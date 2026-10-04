import '../constants/api_paths.dart';
import '../models/clinical_fact.dart';
import '../models/json_utils.dart';
import '../models/medication.dart';
import '../networking/api_client.dart';
import 'demo_store.dart';

/// `/api/v1/facts` — plan §9.6 (the trust layer).
class FactRepository {
  FactRepository(this._client);

  final ApiClient _client;

  /// `GET /patients/{id}/facts?type=&status=&min_conf=`.
  Future<List<ClinicalFact>> list(
    String patientId, {
    FactTypeFilter? type,
    VerificationFilter? status,
    double? minConfidence,
  }) async {
    final String? typeWire;
    switch (type) {
      case null:
        typeWire = null;
      case FactTypeFilter.all:
        typeWire = null;
      case FactTypeFilter.diagnosis:
        typeWire = 'diagnosis';
      case FactTypeFilter.symptom:
        typeWire = 'symptom';
      case FactTypeFilter.medication:
        typeWire = 'medication';
      case FactTypeFilter.investigation:
        typeWire = 'investigation';
      case FactTypeFilter.allergy:
        typeWire = 'allergy';
    }
    try {
      final res = await _client.get<dynamic>(
        ApiPaths.facts(patientId),
        query: <String, dynamic>{
          'type': typeWire,
          'status': status?.wire,
          'min_conf': minConfidence,
        },
      );
      return asMapList(res.data)
          .map(ClinicalFact.fromJson)
          .toList(growable: false);
    } catch (_) {
      final bundled = await DemoStore.dataList('assets/demo/facts.json');
      return bundled
          .map((dynamic e) => ClinicalFact.fromJson(asMap(e)))
          .toList(growable: false);
    }
  }

  /// `GET /facts/{id}/evidence`.
  Future<FactEvidence> evidence(String factId) async {
    try {
      final res = await _client.get<dynamic>(
        ApiPaths.factEvidence(factId),
        parse: (dynamic d) => FactEvidence.fromJson(asMap(d)),
      );
      return res.data;
    } catch (_) {
      final bundled = await DemoStore.dataMap('assets/demo/evidence.json');
      if (bundled != null) return FactEvidence.fromJson(bundled);
      rethrow;
    }
  }

  /// `PATCH /facts/{id}` — mark verified / flag.
  Future<FactVerificationResult> verify(
    String factId, {
    required String verificationStatus,
    String? correctedValue,
    String? doctorNote,
  }) async {
    final res = await _client.patch<dynamic>(
      ApiPaths.fact(factId),
      body: <String, dynamic>{
        'verification_status': verificationStatus,
        if (correctedValue != null && correctedValue.isNotEmpty)
          'corrected_value': correctedValue,
        if (doctorNote != null && doctorNote.isNotEmpty)
          'doctor_note': doctorNote,
      },
      parse: (dynamic d) => FactVerificationResult.fromJson(asMap(d)),
    );
    return res.data;
  }
}

enum FactTypeFilter {
  all,
  diagnosis,
  symptom,
  medication,
  investigation,
  allergy
}

enum VerificationFilter {
  all(null),
  unverified('unverified'),
  needsVerification('needs_verification'),
  doctorVerified('doctor_verified');

  const VerificationFilter(this.wire);
  final String? wire;
}

/// `/api/v1/medications` — plan §9.8 / §9.9.
class MedicationRepository {
  MedicationRepository(this._client);

  final ApiClient _client;

  /// `GET /patients/{id}/medications?status=`.
  Future<List<Medication>> list(String patientId, {String? status}) async {
    try {
      final res = await _client.get<dynamic>(
        ApiPaths.medications(patientId),
        query: <String, dynamic>{'status': status},
      );
      return asMapList(res.data)
          .map(Medication.fromJson)
          .toList(growable: false);
    } catch (_) {
      final bundled = await DemoStore.dataList('assets/demo/medications.json');
      return bundled
          .map((dynamic e) => Medication.fromJson(asMap(e)))
          .toList(growable: false);
    }
  }

  /// `GET /patients/{id}/medications/{group_key}/history`.
  ///
  /// The list payload omits `group_key`, so callers pass the canonical name —
  /// the backend matches `group_key == path` **or** `canonical_name == path`.
  Future<List<MedicationHistoryEntry>> history(
      String patientId, String groupKey) async {
    try {
      final res = await _client
          .get<dynamic>(ApiPaths.medicationHistory(patientId, groupKey));
      return asMapList(res.data)
          .map(MedicationHistoryEntry.fromJson)
          .toList(growable: false);
    } catch (_) {
      final bundled =
          await DemoStore.dataList('assets/demo/medication_history.json');
      return bundled
          .map((dynamic e) => MedicationHistoryEntry.fromJson(asMap(e)))
          .toList(growable: false);
    }
  }
}
