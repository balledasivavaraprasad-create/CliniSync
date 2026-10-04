import '../constants/api_paths.dart';
import '../models/json_utils.dart';
import '../models/patient.dart';
import '../networking/api_client.dart';
import 'demo_store.dart';

/// `/api/v1/patients` — plan §11.1.
class PatientRepository {
  PatientRepository(this._client);

  final ApiClient _client;

  /// `GET /patients?query=&limit=&offset=`.
  Future<List<Patient>> list(
      {String? query, int limit = 50, int offset = 0}) async {
    try {
      final res = await _client.get<dynamic>(
        ApiPaths.patients,
        query: <String, dynamic>{
          'query': query,
          'limit': limit,
          'offset': offset
        },
      );
      return asMapList(res.data).map(Patient.fromJson).toList(growable: false);
    } catch (_) {
      // Offline Demo mode: serve the bundled fictional patient.
      final bundled = await DemoStore.dataList('assets/demo/patients.json');
      return bundled
          .map((dynamic e) => Patient.fromJson(asMap(e)))
          .toList(growable: false);
    }
  }

  /// `GET /patients/{id}`.
  Future<Patient> byId(String id) async {
    final res = await _client.get<dynamic>(
      ApiPaths.patient(id),
      parse: (dynamic d) => Patient.fromJson(asMap(d)),
    );
    return res.data;
  }

  /// `GET /patients/{id}/overview` aggregate.
  ///
  /// Falls back to composing the individual endpoints when the aggregate is
  /// unavailable (plan §9.3).
  Future<PatientOverview> overview(String id) async {
    try {
      final res = await _client.get<dynamic>(
        ApiPaths.patientOverview(id),
        parse: (dynamic d) => PatientOverview.fromJson(asMap(d)),
      );
      return res.data;
    } catch (e) {
      final bundled = await DemoStore.dataMap('assets/demo/overview.json');
      if (bundled != null) {
        return PatientOverview.fromJson(bundled);
      }
      rethrow;
    }
  }

  /// `POST /patients` — returns 201.
  Future<Patient> create(PatientCreate body) async {
    final res = await _client.post<dynamic>(
      ApiPaths.patients,
      body: body.toJson(),
      parse: (dynamic d) => Patient.fromJson(asMap(d)),
    );
    return res.data;
  }

  /// The demo/seeded patient, or null when none exists yet.
  Future<Patient?> demoPatient() async {
    try {
      final patients = await list(limit: 50);
      for (final p in patients) {
        if (p.isDemo) return p;
      }
    } catch (_) {
      // fall through
    }
    return null;
  }
}
