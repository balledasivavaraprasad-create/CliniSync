import 'dart:io';

import '../constants/api_paths.dart';
import '../models/clinical_memory.dart';
import '../models/consultation.dart';
import '../models/doctor_brief.dart';
import '../models/json_utils.dart';
import '../networking/api_client.dart';
import 'demo_store.dart';

/// `/api/v1/brief` — plan §9.14.
class BriefRepository {
  BriefRepository(this._client);

  final ApiClient _client;

  static const Duration _long = Duration(seconds: 120);

  /// `POST /patients/{id}/brief {specialty, force_regenerate}`.
  ///
  /// The backend caches on a fact-set fingerprint and returns the cached brief
  /// unless `force_regenerate` is set.
  Future<DoctorBrief> generate(
    String patientId, {
    String specialty = 'general_medicine',
    bool forceRegenerate = false,
  }) async {
    final res = await _client.post<dynamic>(
      ApiPaths.briefGenerate(patientId),
      body: <String, dynamic>{
        'specialty': specialty,
        'force_regenerate': forceRegenerate,
      },
      timeout: _long,
      parse: (dynamic d) => DoctorBrief.fromJson(asMap(d)),
    );
    // The backend now reports `meta.source = "fallback"` when the deterministic
    // template served the request instead of the model, so the screen can say so
    // instead of implying a model wrote it.
    return res.data.withSource(res.meta.source);
  }

  /// `GET /patients/{id}/brief/latest` — 404 when no brief exists yet.
  ///
  /// Reading a stored brief back reports `db`, not how it was generated, so a
  /// brief loaded later is treated as model-written unless the caller knows
  /// otherwise. The persisted `generation_source` is not exposed on this route.
  Future<DoctorBrief> latest(String patientId) async {
    try {
      final res = await _client.get<dynamic>(
        ApiPaths.briefLatest(patientId),
        parse: (dynamic d) => DoctorBrief.fromJson(asMap(d)),
      );
      return res.data;
    } catch (_) {
      final bundled = await DemoStore.dataMap('assets/demo/brief.json');
      if (bundled != null) return DoctorBrief.fromJson(bundled);
      rethrow;
    }
  }
}

/// `/api/v1/consultations` — plan §9.15 – §9.17.
class ConsultationRepository {
  ConsultationRepository(this._client);

  final ApiClient _client;

  /// `POST /patients/{id}/consultations {specialty, brief_id}` — 201.
  Future<Consultation> create(String patientId,
      {String? specialty, String? briefId}) async {
    final res = await _client.post<dynamic>(
      ApiPaths.consultations(patientId),
      body: <String, dynamic>{
        if (specialty != null) 'specialty': specialty,
        if (briefId != null) 'brief_id': briefId,
      },
      parse: (dynamic d) => Consultation.fromJson(asMap(d)),
    );
    return res.data;
  }

  /// `GET /consultations/{id}`.
  Future<Consultation> byId(String id) async {
    final res = await _client.get<dynamic>(
      ApiPaths.consultation(id),
      parse: (dynamic d) => Consultation.fromJson(asMap(d)),
    );
    return res.data;
  }

  /// `PUT /consultations/{id}` — mutates the **current** version in place.
  Future<ConsultationContent> update(
      String id, ConsultationContent content) async {
    final res = await _client.put<dynamic>(
      ApiPaths.consultation(id),
      body: <String, dynamic>{'content': content.toJson()},
      parse: (dynamic d) =>
          ConsultationContent.fromJson(asMap(asMap(d)['content'])),
    );
    return res.data;
  }

  /// `POST /consultations/{id}/versions` — creates a new version row.
  Future<ConsultationVersion> createVersion(
    String id,
    ConsultationContent content, {
    String? changeSummary,
  }) async {
    final res = await _client.post<dynamic>(
      ApiPaths.consultationVersions(id),
      body: <String, dynamic>{
        'content': content.toJson(),
        if (changeSummary != null && changeSummary.isNotEmpty)
          'change_summary': changeSummary,
      },
      parse: (dynamic d) => ConsultationVersion.fromJson(asMap(d)),
    );
    return res.data;
  }

  /// `GET /consultations/{id}/versions`.
  Future<List<ConsultationVersion>> versions(String id) async {
    final res = await _client.get<dynamic>(ApiPaths.consultationVersions(id));
    return asMapList(res.data)
        .map(ConsultationVersion.fromJson)
        .toList(growable: false);
  }

  /// `POST /consultations/{id}/approve/preview` — dry run (never mutates).
  Future<ApprovalPreview> approvalPreview(
    String id, {
    bool acknowledgedUnedited = false,
    String? notes,
  }) async {
    final res = await _client.post<dynamic>(
      ApiPaths.consultationApprovePreview(id),
      body: <String, dynamic>{
        'acknowledged_unedited': acknowledgedUnedited,
        if (notes != null && notes.isNotEmpty) 'notes': notes,
      },
      parse: (dynamic d) => ApprovalPreview.fromJson(asMap(d)),
    );
    return res.data;
  }

  /// `POST /consultations/{id}/approve` — **never retried** (plan §11.2).
  Future<ApprovalResult> approve(
    String id, {
    bool acknowledgedUnedited = false,
    String? notes,
  }) async {
    final res = await _client.post<dynamic>(
      ApiPaths.consultationApprove(id),
      body: <String, dynamic>{
        'acknowledged_unedited': acknowledgedUnedited,
        if (notes != null && notes.isNotEmpty) 'notes': notes,
      },
      allowRetry: false,
      timeout: const Duration(seconds: 120),
      parse: (dynamic d) => ApprovalResult.fromJson(asMap(d)),
    );
    return res.data;
  }
}

/// `/api/v1/memory` — plan §9.18.
class MemoryRepository {
  MemoryRepository(this._client);

  final ApiClient _client;

  /// `GET /patients/{id}/memory` — verified items only.
  Future<List<ClinicalMemoryItem>> verified(String patientId) async {
    try {
      final res = await _client.get<dynamic>(ApiPaths.memory(patientId));
      return asMapList(res.data)
          .map(ClinicalMemoryItem.fromJson)
          .toList(growable: false);
    } catch (_) {
      final bundled = await DemoStore.dataList('assets/demo/memory.json');
      return bundled
          .map((dynamic e) => ClinicalMemoryItem.fromJson(asMap(e)))
          .toList(growable: false);
    }
  }

  /// `GET /patients/{id}/memory/history` — verified + unverified.
  Future<List<ClinicalMemoryItem>> history(String patientId) async {
    final res = await _client.get<dynamic>(ApiPaths.memoryHistory(patientId));
    return asMapList(res.data)
        .map(ClinicalMemoryItem.fromJson)
        .toList(growable: false);
  }
}

/// `/api/v1/patients/{id}/voice` + `/voice/{id}/review` — plan §9.20.
class VoiceRepository {
  VoiceRepository(this._client);

  final ApiClient _client;

  /// `POST /patients/{id}/voice` (multipart) — 201.
  Future<VoiceNote> upload(String patientId, File file,
      {String languageHint = 'en'}) async {
    final res = await _client.upload<dynamic>(
      ApiPaths.voice(patientId),
      file: file,
      fields: <String, dynamic>{'language_hint': languageHint},
      timeout: const Duration(seconds: 120),
      parse: (dynamic d) => VoiceNote.fromJson(asMap(d)),
    );
    return res.data;
  }

  /// `POST /voice/{id}/review` — promotes proposed facts to `medium` confidence.
  Future<VoiceReviewResult> review(String voiceId,
      {String? editedTranscript}) async {
    final res = await _client.post<dynamic>(
      ApiPaths.voiceReview(voiceId),
      body: <String, dynamic>{
        if (editedTranscript != null && editedTranscript.isNotEmpty)
          'edited_transcript': editedTranscript,
      },
      timeout: const Duration(seconds: 120),
      parse: (dynamic d) => VoiceReviewResult.fromJson(asMap(d)),
    );
    return res.data;
  }
}
