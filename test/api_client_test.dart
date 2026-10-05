import 'dart:convert';
import 'dart:typed_data';

import 'package:clinicsync/core/config/app_config.dart';
import 'package:clinicsync/core/constants/api_paths.dart';
import 'package:clinicsync/core/models/json_utils.dart';
import 'package:clinicsync/core/networking/api_client.dart';
import 'package:clinicsync/core/networking/api_exception.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

/// Builds a [Dio] whose adapter answers with a canned envelope, so no HTTP
/// server is needed (plan C11 acceptance).
///
/// The base URL is the **origin**, exactly as `AppConfig.baseUrl` produces it.
/// Paths arrive absolute from `ApiPaths`, already carrying `/api/v1`.
Dio dioReturning(Object body, {int status = 200}) {
  final Dio dio = Dio(BaseOptions(baseUrl: AppConfig.origin));
  dio.httpClientAdapter = _StubAdapter(body, status);
  return dio;
}

class _StubAdapter implements HttpClientAdapter {
  _StubAdapter(this.body, this.status);

  final Object body;
  final int status;
  int calls = 0;

  /// Every URL the client actually put on the wire, so a test can assert the
  /// resolved path rather than trusting the two halves to agree.
  final List<String> urls = <String>[];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    calls++;
    urls.add(options.uri.toString());
    final String payload = jsonEncode(body);
    return ResponseBody.fromString(
      payload,
      status,
      headers: <String, List<String>>{
        Headers.contentTypeHeader: <String>[Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

Map<String, dynamic> envelope(Object data, {String source = 'db'}) => <String, dynamic>{
      'success': true,
      'data': data,
      'meta': <String, dynamic>{'request_id': 'req_test', 'source': source},
    };

void main() {
  group('C11 ApiClient', () {
    test('unwraps {success, data, meta}', () async {
      final ApiClient client = ApiClient(dio: dioReturning(envelope(<dynamic>[1, 2, 3])));
      final ApiEnvelope<List<dynamic>> res = await client.get<List<dynamic>>('/x');
      expect(res.data, <dynamic>[1, 2, 3]);
      expect(res.meta.source, 'db');
      expect(res.meta.requestId, 'req_test');
    });

    test('passes the envelope through the typed parser', () async {
      final ApiClient client = ApiClient(
        dio: dioReturning(envelope(<String, dynamic>{'full_name': 'Ada'})),
      );
      final ApiEnvelope<String> res = await client.get<String>(
        '/x',
        parse: (dynamic d) => asMap(d)['full_name'].toString(),
      );
      expect(res.data, 'Ada');
    });

    test('throws a typed ApiException for a backend error envelope', () async {
      final ApiClient client = ApiClient(dio: dioReturning(<String, dynamic>{
        'success': false,
        'error': <String, dynamic>{'code': 'NOT_FOUND', 'message': 'patient not found.'},
        'meta': <String, dynamic>{'request_id': 'req_test'},
      }));
      await expectLater(
        client.get<dynamic>('/x'),
        throwsA(
          isA<ApiException>()
              .having((ApiException e) => e.code, 'code', 'NOT_FOUND')
              .having((ApiException e) => e.message, 'message', 'patient not found.'),
        ),
      );
    });

    test('never leaks a raw internal error message', () async {
      final ApiClient client = ApiClient(dio: dioReturning(<String, dynamic>{
        'success': false,
        'error': <String, dynamic>{
          'code': 'INTERNAL_ERROR',
          'message': "Traceback (most recent call last): File '/app/main.py' line 88",
        },
      }));
      try {
        await client.get<dynamic>('/x');
        fail('expected an ApiException');
      } on ApiException catch (e) {
        expect(e.message, isNot(contains('Traceback')));
        expect(e.message, isNot(contains('/app/main.py')));
      }
    });

    test('rejects a malformed envelope rather than silently returning null',
        () async {
      final ApiClient client = ApiClient(dio: dioReturning(<String, dynamic>{'data': 1}));
      await expectLater(
        client.get<dynamic>('/x'),
        throwsA(isA<ApiException>()),
      );
    });

    test('drops null and empty query values', () {
      expect(
        ApiClient.cleanQuery(<String, dynamic>{'a': null, 'b': '', 'c': 1}),
        <String, dynamic>{'c': 1},
      );
      expect(ApiClient.cleanQuery(null), isNull);
      expect(ApiClient.cleanQuery(<String, dynamic>{}), isNull);
    });

    test('GET retries once on a 5xx and then surfaces the error', () async {
      final Dio dio = Dio(BaseOptions(baseUrl: 'http://localhost:8000/api/v1'));
      int attempts = 0;
      dio.httpClientAdapter = _CountingAdapter(() {
        attempts++;
        return ResponseBody.fromString('{}', 503, headers: <String, List<String>>{
          Headers.contentTypeHeader: <String>[Headers.jsonContentType],
        });
      });
      final ApiClient client = ApiClient(dio: dio);
      await expectLater(client.get<dynamic>('/x'), throwsA(isA<ApiException>()));
      expect(attempts, 2, reason: 'one retry for a GET on 5xx');
    });

    test('POST is never retried', () async {
      final Dio dio = Dio(BaseOptions(baseUrl: 'http://localhost:8000/api/v1'));
      int attempts = 0;
      dio.httpClientAdapter = _CountingAdapter(() {
        attempts++;
        return ResponseBody.fromString('{}', 503, headers: <String, List<String>>{
          Headers.contentTypeHeader: <String>[Headers.jsonContentType],
        });
      });
      final ApiClient client = ApiClient(dio: dio);
      await expectLater(client.post<dynamic>('/x'), throwsA(isA<ApiException>()));
      expect(attempts, 1, reason: 'POST approve must never be retried');
    });
  });

  group('the client and the backend agree on one /api/v1', () {
    test('the dio base URL carries no path of its own', () {
      // Every path in ApiPaths is absolute and already starts with /api/v1, so
      // a base URL that adds the prefix makes every request go out as
      // /api/v1/api/v1/… — which used to work only because the backend has a
      // middleware that silently collapses it.
      expect(AppConfig.baseUrl, isNot(contains('/api/v1')));
      expect(AppConfig.baseUrl, AppConfig.origin);
    });

    test('no path doubles the prefix on the wire', () async {
      final _StubAdapter adapter = _StubAdapter(envelope(<dynamic>[]), 200);
      final Dio dio = Dio(BaseOptions(baseUrl: AppConfig.baseUrl))
        ..httpClientAdapter = adapter;
      final ApiClient client = ApiClient(dio: dio);

      await client.get<dynamic>(ApiPaths.issues('pat_demo_patient_001'));
      await client.get<dynamic>(ApiPaths.healthDeep);
      await client.post<dynamic>(
        ApiPaths.briefGenerate('pat_demo_patient_001'),
        body: <String, dynamic>{'specialty': 'general_medicine'},
      );

      expect(adapter.urls, hasLength(3));
      for (final String url in adapter.urls) {
        expect(
          url,
          isNot(contains('/api/v1/api/v1')),
          reason: '$url has a doubled prefix',
        );
        expect(url, contains('/api/v1/'));
        expect(
          url,
          startsWith('${AppConfig.origin}/api/v1'),
          reason: 'a request must resolve against the configured origin',
        );
      }
    });

    test('every declared path starts with the version prefix exactly once', () {
      // Guards the other half of the contract: a path added without `$v1` would
      // silently fall back to whatever the base URL happened to carry.
      final List<String> paths = <String>[
        ApiPaths.health,
        ApiPaths.healthDeep,
        ApiPaths.specialties,
        ApiPaths.patients,
        ApiPaths.patient('p'),
        ApiPaths.patientOverview('p'),
        ApiPaths.documents('p'),
        ApiPaths.document('d'),
        ApiPaths.documentFile('d'),
        ApiPaths.documentStatus('d'),
        ApiPaths.documentProcess('d'),
        ApiPaths.documentReprocess('d'),
        ApiPaths.documentPage('d', 1),
        ApiPaths.facts('p'),
        ApiPaths.fact('f'),
        ApiPaths.factEvidence('f'),
        ApiPaths.timeline('p'),
        ApiPaths.medications('p'),
        ApiPaths.medicationHistory('p', 'g'),
        ApiPaths.investigations('p'),
        ApiPaths.investigationTrend('p', 'g'),
        ApiPaths.issues('p'),
        ApiPaths.briefLatest('p'),
        ApiPaths.briefGenerate('p'),
        ApiPaths.consultations('p'),
        ApiPaths.memory('p'),
        ApiPaths.memoryHistory('p'),
        ApiPaths.voice('p'),
        ApiPaths.voiceReview('v'),
        ApiPaths.issuesRecompute('p'),
        ApiPaths.issue('i'),
        ApiPaths.consultation('c'),
        ApiPaths.consultationVersions('c'),
        ApiPaths.consultationApprovePreview('c'),
        ApiPaths.consultationApprove('c'),
      ];
      for (final String path in paths) {
        expect(path, startsWith('${ApiPaths.v1}/'),
            reason: '$path is missing the version prefix');
      }
    });
  });
}

class _CountingAdapter implements HttpClientAdapter {
  _CountingAdapter(this.respond);

  final ResponseBody Function() respond;
  int calls = 0;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    calls++;
    return respond();
  }

  @override
  void close({bool force = false}) {}
}
