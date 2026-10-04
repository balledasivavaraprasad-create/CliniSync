import 'dart:io';

import 'package:dio/dio.dart';

import '../constants/api_paths.dart';
import '../constants/enums.dart';
import '../models/document.dart';
import '../models/json_utils.dart';
import '../networking/api_client.dart';
import '../networking/api_exception.dart';
import 'demo_store.dart';

/// `/api/v1/documents` — plan §9.4 / §9.5.
class DocumentRepository {
  DocumentRepository(this._client);

  final ApiClient _client;

  /// Long-running: process / upload use 120 s (plan §11.2).
  static const Duration _long = Duration(seconds: 120);

  Future<List<ClinicalDocument>> list(String patientId) async {
    try {
      final res = await _client.get<dynamic>(ApiPaths.documents(patientId));
      return asMapList(res.data)
          .map(ClinicalDocument.fromJson)
          .toList(growable: false);
    } catch (_) {
      final bundled = await DemoStore.dataList('assets/demo/documents.json');
      return bundled
          .map((dynamic e) => ClinicalDocument.fromJson(asMap(e)))
          .toList(growable: false);
    }
  }

  Future<ClinicalDocument> byId(String documentId) async {
    final res = await _client.get<dynamic>(
      ApiPaths.document(documentId),
      parse: (dynamic d) => ClinicalDocument.fromJson(asMap(d)),
    );
    return res.data;
  }

  /// `POST /patients/{id}/documents` (multipart).
  ///
  /// The backend dedupes by SHA-256 and answers 201 with the **existing**
  /// document and `duplicate: true` when the file is already stored.
  Future<ClinicalDocument> upload(
    String patientId,
    File file, {
    String uploadedVia = 'upload',
    String? documentTypeHint,
    ProgressCallback? onProgress,
  }) async {
    final res = await _client.upload<dynamic>(
      ApiPaths.documents(patientId),
      file: file,
      fields: <String, dynamic>{
        'uploaded_via': uploadedVia,
        if (documentTypeHint != null) 'document_type_hint': documentTypeHint,
      },
      timeout: _long,
      onSendProgress: onProgress,
      parse: (dynamic d) => ClinicalDocument.fromJson(asMap(d)),
    );
    return res.data;
  }

  /// `GET /documents/{id}/status` — polled every 1.5 s by the Processing screen.
  Future<ProcessingStatusSnapshot> status(String documentId) async {
    try {
      final res = await _client.get<dynamic>(
        ApiPaths.documentStatus(documentId),
        parse: (dynamic d) => ProcessingStatusSnapshot.fromJson(asMap(d)),
      );
      return res.data;
    } catch (_) {
      final bundled =
          await DemoStore.dataMap('assets/demo/document_status.json');
      if (bundled != null) return ProcessingStatusSnapshot.fromJson(bundled);
      throw const ApiException(
          code: 'NOT_FOUND', message: 'We couldn\'t find that record.');
    }
  }

  /// `POST /documents/{id}/process` — fires the pipeline in the background.
  Future<ProcessingStatus> process(String documentId) async {
    final res = await _client.post<dynamic>(
      ApiPaths.documentProcess(documentId),
      timeout: _long,
      parse: (dynamic d) => ProcessingStatus.fromWire(asMap(d)['status']),
    );
    return res.data;
  }

  /// `POST /documents/{id}/reprocess`.
  Future<ProcessingStatus> reprocess(String documentId) async {
    final res = await _client.post<dynamic>(
      ApiPaths.documentReprocess(documentId),
      timeout: _long,
      parse: (dynamic d) => ProcessingStatus.fromWire(asMap(d)['status']),
    );
    return res.data;
  }

  /// `GET /documents/{id}/pages/{n}` — optional source-page render.
  Future<DocumentPage?> page(String documentId, int pageNumber) async {
    try {
      final res = await _client.get<dynamic>(
        ApiPaths.documentPage(documentId, pageNumber),
        parse: (dynamic d) => DocumentPage.fromJson(asMap(d)),
      );
      return res.data;
    } catch (_) {
      return null;
    }
  }

  /// `GET /documents/{id}/file` — **not** enveloped; returns raw bytes.
  Future<List<int>> file(String documentId) =>
      _client.getBytes(ApiPaths.documentFile(documentId));
}
