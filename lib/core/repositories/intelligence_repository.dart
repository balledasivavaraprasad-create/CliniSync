import '../constants/api_paths.dart';
import '../models/investigation.dart';
import '../models/json_utils.dart';
import '../models/timeline_event.dart';
import '../networking/api_client.dart';
import 'demo_store.dart';

/// `/api/v1/timeline` — plan §9.7.
class TimelineRepository {
  TimelineRepository(this._client);

  final ApiClient _client;

  /// `GET /patients/{id}/timeline?from=&to=&type=&limit=`.
  ///
  /// Note: the backend performs **no** patient-existence check, so an unknown
  /// patient returns `[]` with HTTP 200.
  Future<List<TimelineEvent>> list(
    String patientId, {
    String? from,
    String? to,
    String? type,
    int limit = 100,
  }) async {
    try {
      final res = await _client.get<dynamic>(
        ApiPaths.timeline(patientId),
        query: <String, dynamic>{
          'from': from,
          'to': to,
          'type': type,
          'limit': limit
        },
      );
      return asMapList(res.data)
          .map(TimelineEvent.fromJson)
          .toList(growable: false);
    } catch (_) {
      final bundled = await DemoStore.dataList('assets/demo/timeline.json');
      return bundled
          .map((dynamic e) => TimelineEvent.fromJson(asMap(e)))
          .toList(growable: false);
    }
  }
}

/// `/api/v1/investigations` — plan §9.10 / §9.11.
class InvestigationRepository {
  InvestigationRepository(this._client);

  final ApiClient _client;

  /// `GET /patients/{id}/investigations` — latest value per test.
  Future<List<Investigation>> list(String patientId) async {
    try {
      final res =
          await _client.get<dynamic>(ApiPaths.investigations(patientId));
      return asMapList(res.data)
          .map(Investigation.fromJson)
          .toList(growable: false);
    } catch (_) {
      final bundled =
          await DemoStore.dataList('assets/demo/investigations.json');
      return bundled
          .map((dynamic e) => Investigation.fromJson(asMap(e)))
          .toList(growable: false);
    }
  }

  /// `GET /patients/{id}/investigations/{group_key}/trend`.
  ///
  /// With no measurements the backend answers 200 with an **empty series** and
  /// omits `unit` / `latest_value` / `latest_flag`, so every field is nullable.
  Future<InvestigationTrend> trend(String patientId, String groupKey) async {
    try {
      final res = await _client.get<dynamic>(
        ApiPaths.investigationTrend(patientId, groupKey),
        parse: (dynamic d) => InvestigationTrend.fromJson(asMap(d)),
      );
      return res.data;
    } catch (_) {
      final bundled = await DemoStore.dataMap('assets/demo/trend_hba1c.json');
      if (bundled != null) return InvestigationTrend.fromJson(bundled);
      rethrow;
    }
  }
}

/// `/api/v1/issues` — plan §9.12 (the clinical review queue).
class IssueRepository {
  IssueRepository(this._client);

  final ApiClient _client;

  /// `GET /patients/{id}/issues?type=&status=&severity=`.
  Future<List<ClinicalIssue>> list(
    String patientId, {
    String? type,
    String? status,
    String? severity,
  }) async {
    try {
      final res = await _client.get<dynamic>(
        ApiPaths.issues(patientId),
        query: <String, dynamic>{
          'type': type,
          'status': status,
          'severity': severity
        },
      );
      return asMapList(res.data)
          .map(ClinicalIssue.fromJson)
          .toList(growable: false);
    } catch (_) {
      final bundled = await DemoStore.dataList('assets/demo/issues.json');
      return bundled
          .map((dynamic e) => ClinicalIssue.fromJson(asMap(e)))
          .toList(growable: false);
    }
  }

  /// `PATCH /issues/{id}` — acknowledge / dismiss.
  ///
  /// NOTE: the backend raises `ValueError` (HTTP 500) rather than 404 for an
  /// unknown id — logged in `docs/frontend/API_MISMATCHES.md`.
  Future<IssuePatchResult> patch(
    String issueId, {
    required String status,
    String? doctorNote,
  }) async {
    final res = await _client.patch<dynamic>(
      ApiPaths.issue(issueId),
      body: <String, dynamic>{
        'status': status,
        if (doctorNote != null) 'doctor_note': doctorNote
      },
      parse: (dynamic d) => IssuePatchResult.fromJson(asMap(d)),
    );
    return res.data;
  }

  /// `POST /patients/{id}/issues/recompute`.
  Future<List<ClinicalIssue>> recompute(String patientId) async {
    final res = await _client.post<dynamic>(
      ApiPaths.issuesRecompute(patientId),
      timeout: const Duration(seconds: 120),
    );
    return asMapList(res.data)
        .map(ClinicalIssue.fromJson)
        .toList(growable: false);
  }
}
