/// Route names — plan §8 navigation map.
abstract final class RouteNames {
  const RouteNames._();

  // ── Shell tabs
  static const String home = 'home';
  static const String patients = 'patients';
  static const String records = 'records';
  static const String memory = 'memory';

  // ── Push-only
  static const String patientOverview = 'patient-overview';
  static const String patientTimeline = 'patient-timeline';
  static const String patientMedications = 'patient-medications';
  static const String patientInvestigations = 'patient-investigations';
  static const String patientIssues = 'patient-issues';
  static const String medicationReconcile = 'medication-reconcile';
  static const String investigationTrend = 'investigation-trend';
  static const String patientDocuments = 'patient-documents';
  static const String patientFacts = 'patient-facts';
  static const String specialty = 'specialty';
  static const String brief = 'brief';
  static const String consultation = 'consultation';
  static const String consultationVersions = 'consultation-versions';
  static const String approval = 'approval';
  static const String patientMemory = 'patient-memory';
  static const String processing = 'document-processing';
  static const String factEvidence = 'fact-evidence';
  static const String camera = 'camera';
  static const String voice = 'voice';

  // ── Debug / galleries (task C06/C08/C10 acceptance)
  static const String componentGallery = 'component-gallery';
  static const String tokenGallery = 'token-gallery';
}

/// Typed argument bundles for routes that take parameters.
class OverviewArgs {
  const OverviewArgs({required this.patientId, this.patientName});

  final String patientId;
  final String? patientName;
}

class ReconcileArgs {
  const ReconcileArgs(
      {required this.patientId, required this.groupKey, this.medicationName});

  final String patientId;

  /// Canonical medication name — the backend matches `group_key == path` **or**
  /// `canonical_name == path`, and the list payload has no `group_key`.
  final String groupKey;
  final String? medicationName;
}

class TrendArgs {
  const TrendArgs(
      {required this.patientId, required this.groupKey, this.testName});

  final String patientId;
  final String groupKey;
  final String? testName;
}

class SpecialtyArgs {
  const SpecialtyArgs(
      {this.patientId, this.title = 'Specialty', this.onSelected});

  final String? patientId;
  final String title;
  final void Function(String wire)? onSelected;
}

class BriefArgs {
  const BriefArgs({required this.patientId, this.specialty});

  final String patientId;
  final String? specialty;
}

class ConsultationArgs {
  const ConsultationArgs({
    required this.patientId,
    this.consultationId,
    this.specialty,
    this.briefId,
  });

  final String patientId;
  final String? consultationId;
  final String? specialty;
  final String? briefId;
}

class ConsultationVersionsArgs {
  const ConsultationVersionsArgs({
    required this.patientId,
    required this.consultationId,
  });

  final String patientId;
  final String consultationId;
}

class ApprovalArgs {
  const ApprovalArgs({required this.patientId, required this.consultationId});

  final String patientId;
  final String consultationId;
}

class DocumentsArgs {
  const DocumentsArgs({required this.patientId, this.filter});

  final String patientId;
  final String? filter;
}

class FactsArgs {
  const FactsArgs({required this.patientId, this.initialTab});

  final String patientId;
  final int? initialTab;
}

class ProcessingArgs {
  const ProcessingArgs(
      {required this.patientId, required this.documentId, this.documentName});

  final String patientId;
  final String documentId;
  final String? documentName;
}

class EvidenceArgs {
  const EvidenceArgs({required this.factId, this.patientId});

  final String factId;
  final String? patientId;
}

class CameraArgs {
  const CameraArgs({required this.patientId});

  final String patientId;
}

class VoiceArgs {
  const VoiceArgs({required this.patientId});

  final String patientId;
}

class PatientMemoryArgs {
  const PatientMemoryArgs({required this.patientId});

  final String patientId;
}
