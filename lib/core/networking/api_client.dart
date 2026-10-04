import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart' show visibleForTesting;

import '../config/app_config.dart';
import 'api_exception.dart';
import 'error_messages.dart';

/// A parsed API envelope: `{success, data, meta}` — plan §10.
class ApiEnvelope<T> {
  const ApiEnvelope({required this.data, required this.meta});

  final T data;
  final ApiMeta meta;
}

/// The `meta` block.
///
/// `source == "fallback"` is **never emitted** by the current backend (logged in
/// `docs/frontend/API_MISMATCHES.md`), so repositories derive the `Demo data`
/// tag from whether they actually served a bundled fixture instead.
class ApiMeta {
  const ApiMeta({required this.requestId, required this.source});

  final String requestId;

  /// `db` | `llm` | `system` | `stt`.
  final String source;

  bool get isLlm => source == 'llm';
  bool get isFallback => source == 'fallback';

  static const ApiMeta empty = ApiMeta(requestId: 'req_direct', source: 'db');
}

/// Single HTTP client — plan §11.2.
///
/// * 30 s default timeout, 120 s for process / brief / voice.
/// * one retry on network/5xx for **GET only**; never retry `POST approve`.
/// * uploads report progress.
class ApiClient {
  ApiClient({Dio? dio})
      : _dio = dio ??
            Dio(
              BaseOptions(
                baseUrl: AppConfig.baseUrl,
                connectTimeout: const Duration(seconds: 12),
                receiveTimeout: const Duration(seconds: 30),
                sendTimeout: const Duration(seconds: 30),
                headers: const <String, dynamic>{
                  'Accept': 'application/json',
                  'X-Request-ID': 'req_flutter',
                },
                // Non-2xx is handled by the envelope parser, not by dio.
                validateStatus: (int? status) => status != null && status < 500,
              ),
            ) {
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (RequestOptions options, RequestInterceptorHandler handler) {
          // Re-read the base URL each call so runtime changes take effect.
          options.baseUrl = AppConfig.baseUrl;
          handler.next(options);
        },
      ),
    );
  }

  final Dio _dio;

  Dio get raw => _dio;

  String get baseUrl => AppConfig.baseUrl;

  // ── GET ────────────────────────────────────────────────────────────────

  Future<ApiEnvelope<T>> get<T>(
    String path, {
    Map<String, dynamic>? query,
    Duration? timeout,
    T Function(dynamic data)? parse,
    bool allowRetry = true,
  }) async {
    final Response<dynamic> response = await _send(
      () => _dio.get<dynamic>(
        path,
        queryParameters: cleanQuery(query),
        options: Options(
          responseType: ResponseType.json,
          receiveTimeout: timeout ?? const Duration(seconds: 30),
        ),
      ),
      allowRetry: allowRetry,
    );
    return _envelope<T>(response, parse);
  }

  // ── POST / PUT / PATCH / DELETE ────────────────────────────────────────

  Future<ApiEnvelope<T>> post<T>(
    String path, {
    Object? body,
    Map<String, dynamic>? query,
    Duration? timeout,
    T Function(dynamic data)? parse,
    bool allowRetry = false,
    ProgressCallback? onSendProgress,
  }) async {
    final Response<dynamic> response = await _send(
      () => _dio.post<dynamic>(
        path,
        data: body,
        queryParameters: cleanQuery(query),
        onSendProgress: onSendProgress,
        options: Options(
          responseType: ResponseType.json,
          receiveTimeout: timeout ?? const Duration(seconds: 30),
          sendTimeout: timeout ?? const Duration(seconds: 30),
        ),
      ),
      allowRetry: allowRetry,
    );
    return _envelope<T>(response, parse);
  }

  Future<ApiEnvelope<T>> put<T>(
    String path, {
    Object? body,
    Duration? timeout,
    T Function(dynamic data)? parse,
  }) async {
    final Response<dynamic> response = await _send(
      () => _dio.put<dynamic>(
        path,
        data: body,
        options: Options(
          responseType: ResponseType.json,
          receiveTimeout: timeout ?? const Duration(seconds: 30),
        ),
      ),
      allowRetry: false,
    );
    return _envelope<T>(response, parse);
  }

  Future<ApiEnvelope<T>> patch<T>(
    String path, {
    Object? body,
    T Function(dynamic data)? parse,
  }) async {
    final Response<dynamic> response = await _send(
      () => _dio.patch<dynamic>(
        path,
        data: body,
        options: Options(responseType: ResponseType.json),
      ),
      allowRetry: false,
    );
    return _envelope<T>(response, parse);
  }

  Future<ApiEnvelope<T>> delete<T>(
    String path, {
    T Function(dynamic data)? parse,
  }) async {
    final Response<dynamic> response = await _send(
      () => _dio.delete<dynamic>(path,
          options: Options(responseType: ResponseType.json)),
      allowRetry: false,
    );
    return _envelope<T>(response, parse);
  }

  // ── Multipart upload ───────────────────────────────────────────────────

  Future<ApiEnvelope<T>> upload<T>(
    String path, {
    required File file,
    String fieldName = 'file',
    Map<String, dynamic> fields = const <String, dynamic>{},
    Duration? timeout,
    T Function(dynamic data)? parse,
    ProgressCallback? onSendProgress,
  }) async {
    final FormData form = FormData.fromMap(<String, dynamic>{
      ...fields,
      fieldName: await MultipartFile.fromFile(file.path,
          filename: basename(file.path)),
    });
    final Response<dynamic> response = await _send(
      () => _dio.post<dynamic>(
        path,
        data: form,
        onSendProgress: onSendProgress,
        options: Options(
          responseType: ResponseType.json,
          receiveTimeout: timeout ?? const Duration(seconds: 120),
          sendTimeout: timeout ?? const Duration(seconds: 120),
        ),
      ),
      allowRetry: false,
    );
    return _envelope<T>(response, parse);
  }

  /// Raw file bytes — `GET /documents/{id}/file` is **not** enveloped.
  Future<List<int>> getBytes(String path, {Duration? timeout}) async {
    final Response<dynamic> response = await _send(
      () => _dio.get<List<int>>(
        path,
        options: Options(
          responseType: ResponseType.bytes,
          receiveTimeout: timeout ?? const Duration(seconds: 60),
        ),
      ),
      allowRetry: true,
    );
    final dynamic data = response.data;
    if (data == null) {
      throw const ApiException(
          code: 'MALFORMED_ENVELOPE', message: ErrorMessages.unknown);
    }
    return data;
  }

  // ── Internals ──────────────────────────────────────────────────────────

  static String basename(String path) {
    final int i = path.lastIndexOf(RegExp(r'[/\\]'));
    return i == -1 ? path : path.substring(i + 1);
  }

  /// Drops null and empty-string query values so optional filters are omitted.
  @visibleForTesting
  static Map<String, dynamic>? cleanQuery(Map<String, dynamic>? query) {
    if (query == null || query.isEmpty) return null;
    final Map<String, dynamic> out = <String, dynamic>{};
    query.forEach((String k, dynamic v) {
      if (v == null) return;
      if (v is String && v.isEmpty) return;
      out[k] = v;
    });
    return out.isEmpty ? null : out;
  }

  Future<Response<dynamic>> _send(
    Future<Response<dynamic>> Function() request, {
    required bool allowRetry,
  }) async {
    int attempt = 0;
    while (true) {
      try {
        final Response<dynamic> response = await request();
        final int? status = response.statusCode;
        if (status != null && status >= 500) {
          if (allowRetry && attempt < 1) {
            attempt++;
            await Future<void>.delayed(const Duration(milliseconds: 350));
            continue;
          }
          throw ApiException(
            code: 'INTERNAL_ERROR',
            message: ErrorMessages.unknown,
            statusCode: status,
          );
        }
        return response;
      } on DioException catch (e) {
        if (allowRetry && attempt < 1 && _isRetryable(e)) {
          attempt++;
          await Future<void>.delayed(const Duration(milliseconds: 350));
          continue;
        }
        throw mapDioError(e);
      }
    }
  }

  static bool _isRetryable(DioException e) {
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
      case DioExceptionType.connectionError:
        return true;
      case DioExceptionType.badResponse:
        final int? status = e.response?.statusCode;
        return status != null && status >= 500;
      case DioExceptionType.cancel:
      case DioExceptionType.badCertificate:
      case DioExceptionType.unknown:
      case DioExceptionType.transformTimeout:
        return false;
    }
  }

  @visibleForTesting
  static ApiException mapDioError(DioException e) {
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return const ApiException(
            code: 'TIMEOUT', message: ErrorMessages.timeout, isNetwork: true);
      case DioExceptionType.connectionError:
      case DioExceptionType.unknown:
      case DioExceptionType.badCertificate:
        return const ApiException(
            code: 'NETWORK', message: ErrorMessages.network, isNetwork: true);
      case DioExceptionType.cancel:
        return const ApiException(
            code: 'CANCELLED', message: 'That request was cancelled.');
      case DioExceptionType.transformTimeout:
        return const ApiException(
            code: 'MALFORMED_ENVELOPE', message: ErrorMessages.unknown);
      case DioExceptionType.badResponse:
        return ApiException(
          code: 'HTTP_ERROR',
          message: ErrorMessages.unknown,
          statusCode: e.response?.statusCode,
        );
    }
  }

  ApiEnvelope<T> _envelope<T>(
      Response<dynamic> response, T Function(dynamic data)? parse) {
    final int status = response.statusCode ?? 200;
    final dynamic body = response.data;

    if (body is List<int>) {
      throw const ApiException(
          code: 'MALFORMED_ENVELOPE', message: ErrorMessages.unknown);
    }

    if (body is! Map) {
      if (status >= 200 && status < 300) {
        return ApiEnvelope<T>(data: parse!(body), meta: ApiMeta.empty);
      }
      throw ApiException(
          code: 'HTTP_ERROR',
          message: ErrorMessages.unknown,
          statusCode: status);
    }

    final Map<String, dynamic> map = Map<String, dynamic>.from(body);
    if (map['success'] != true) {
      final dynamic error = map['error'];
      final String? code = error is Map ? error['code']?.toString() : null;
      final String? message =
          error is Map ? error['message']?.toString() : null;
      final Map<String, dynamic>? details =
          error is Map && error['details'] is Map
              ? Map<String, dynamic>.from(error['details'] as Map)
              : null;
      throw ApiException(
        code: code ?? 'HTTP_ERROR',
        // The backend already writes doctor-facing sentences; we only tidy
        // them and fall back to the §11.4 map for machine-ish codes.
        message: _humanise(message, code),
        statusCode: status,
        details: details,
      );
    }

    final dynamic metaRaw = map['meta'];
    final ApiMeta meta = metaRaw is Map
        ? ApiMeta(
            requestId: metaRaw['request_id']?.toString() ?? 'req_direct',
            source: metaRaw['source']?.toString() ?? 'db',
          )
        : ApiMeta.empty;

    return ApiEnvelope<T>(
        data: parse != null ? parse(map['data']) : map['data'] as T,
        meta: meta);
  }

  static String _humanise(String? message, String? code) {
    if (message == null || message.trim().isEmpty) {
      return ErrorMessages.forCode(code);
    }
    if (code != null &&
        (code.toUpperCase() == 'INTERNAL_ERROR' ||
            code.toUpperCase() == 'HTTP_ERROR')) {
      return ErrorMessages.unknown;
    }
    String m = message.trim();
    if (!m.endsWith('.')) m = '$m.';
    return m;
  }
}
