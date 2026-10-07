/// API path constants — plan §8, §11.1.
///
/// Mirrors `backend/app/api/routes/*` exactly. The base URL comes from
/// [AppConfig]; nothing here contains a host.
abstract final class ApiPaths {
  const ApiPaths._();

  static const String v1 = '/api/v1';

  // ── Health ─────────────────────────────────────────────────────────────
  static const String health = '$v1/health';
  static const String healthDeep = '$v1/health/deep';

  // ── Auth ───────────────────────────────────────────────────────────────
  static const String login = '$v1/auth/login';
  static const String register = '$v1/auth/register';
  static const String authMe = '$v1/auth/me';
  static const String logout = '$v1/auth/logout';

  // ── Reference data ─────────────────────────────────────────────────────
  static const String specialties = '$v1/specialties';

  // ── Patients ───────────────────────────────────────────────────────────
  static const String patients = '$v1/patients';
  static String patient(String id) => '$v1/patients/$id';
  static String patientOverview(String id) => '$v1/patients/$id/overview';

  // ── Documents ──────────────────────────────────────────────────────────
  static String documents(String patientId) =>
      '$v1/patients/$patientId/documents';
  static String document(String documentId) => '$v1/documents/$documentId';
  static String documentFile(String documentId) =>
      '$v1/documents/$documentId/file';
  static String documentStatus(String documentId) =>
      '$v1/documents/$documentId/status';
  static String documentProcess(String documentId) =>
      '$v1/documents/$documentId/process';
  static String documentReprocess(String documentId) =>
      '$v1/documents/$documentId/reprocess';
  static String documentPage(String documentId, int page) =>
      '$v1/documents/$documentId/pages/$page';

  // ── Facts & evidence ───────────────────────────────────────────────────
  static String facts(String patientId) => '$v1/patients/$patientId/facts';
  static String factEvidence(String factId) => '$v1/facts/$factId/evidence';
  static String fact(String factId) => '$v1/facts/$factId';

  // ── Timeline ───────────────────────────────────────────────────────────
  static String timeline(String patientId) =>
      '$v1/patients/$patientId/timeline';

  // ── Medications ────────────────────────────────────────────────────────
  static String medications(String patientId) =>
      '$v1/patients/$patientId/medications';
  static String medicationHistory(String patientId, String groupKey) =>
      '$v1/patients/$patientId/medications/$groupKey/history';

  // ── Investigations ─────────────────────────────────────────────────────
  static String investigations(String patientId) =>
      '$v1/patients/$patientId/investigations';
  static String investigationTrend(String patientId, String groupKey) =>
      '$v1/patients/$patientId/investigations/$groupKey/trend';

  // ── Issues ─────────────────────────────────────────────────────────────
  static String issues(String patientId) => '$v1/patients/$patientId/issues';
  static String issuesRecompute(String patientId) =>
      '$v1/patients/$patientId/issues/recompute';
  static String issue(String issueId) => '$v1/issues/$issueId';

  // ── Briefs ─────────────────────────────────────────────────────────────
  static String briefGenerate(String patientId) =>
      '$v1/patients/$patientId/brief';
  static String briefLatest(String patientId) =>
      '$v1/patients/$patientId/brief/latest';

  // ── Consultations ──────────────────────────────────────────────────────
  static String consultations(String patientId) =>
      '$v1/patients/$patientId/consultations';
  static String consultation(String id) => '$v1/consultations/$id';
  static String consultationVersions(String id) =>
      '$v1/consultations/$id/versions';
  static String consultationApprovePreview(String id) =>
      '$v1/consultations/$id/approve/preview';
  static String consultationApprove(String id) =>
      '$v1/consultations/$id/approve';

  // ── Memory ─────────────────────────────────────────────────────────────
  static String memory(String patientId) => '$v1/patients/$patientId/memory';
  static String memoryHistory(String patientId) =>
      '$v1/patients/$patientId/memory/history';

  // ── Voice ──────────────────────────────────────────────────────────────
  static String voice(String patientId) => '$v1/patients/$patientId/voice';
  static String voiceReview(String voiceId) => '$v1/voice/$voiceId/review';
}
