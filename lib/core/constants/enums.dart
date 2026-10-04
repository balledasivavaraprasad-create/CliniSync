/// Domain enums mirroring the backend's emitted strings.
///
/// Every enum parses tolerantly: an unknown wire value degrades to a safe member
/// instead of throwing (plan §8 "Tolerant parsing").
library;

/// `DocumentType`.
enum RecordType {
  prescription('prescription', 'Prescription', 'pill'),
  labReport('lab_report', 'Lab report', 'testTube'),
  consultationNote('consultation_note', 'Consultation note', 'notebook'),
  dischargeSummary('discharge_summary', 'Discharge summary', 'logOut'),
  diagnosticReport('diagnostic_report', 'Diagnostic report', 'activity'),
  imagingReport('imaging_report', 'Imaging report', 'scanLine'),
  referral('referral', 'Referral', 'cornerUpLeft'),
  other('other', 'Other record', 'fileText'),
  unknown('unknown', 'Unclassified', 'file');

  const RecordType(this.wire, this.label, this.icon);

  final String wire;
  final String label;

  /// Name in `AppIcons.table`.
  final String icon;

  static RecordType fromWire(Object? raw) {
    final String s = raw?.toString().trim().toLowerCase() ?? '';
    for (final RecordType v in RecordType.values) {
      if (v.wire == s) return v;
    }
    return RecordType.unknown;
  }
}

/// `ProcessingStatus`.
enum ProcessingStatus {
  uploaded('uploaded', 'Uploaded'),
  extractingText('extracting_text', 'Extracting text'),
  classifying('classifying', 'Classifying'),
  extractingEntities('extracting_entities', 'Extracting clinical information'),
  normalizing('normalizing', 'Normalising & linking evidence'),
  validating('validating', 'Validating'),
  complete('complete', 'Complete'),
  needsReview('needs_review', 'Needs review'),
  failed('failed', 'Failed');

  const ProcessingStatus(this.wire, this.label);

  final String wire;
  final String label;

  bool get isTerminal =>
      this == complete || this == needsReview || this == failed;
  bool get isFailed => this == failed;
  bool get isRunning => !isTerminal && this != uploaded;

  static ProcessingStatus fromWire(Object? raw) {
    final String s = raw?.toString().trim().toLowerCase() ?? '';
    for (final ProcessingStatus v in ProcessingStatus.values) {
      if (v.wire == s) return v;
    }
    return ProcessingStatus.uploaded;
  }
}

/// The 6 pipeline stages rendered by the Processing stepper — plan §9.5.
enum PipelineStage {
  uploaded('uploaded', 'Uploaded'),
  extractingText('extracting_text', 'Extracting Text'),
  classifying('classifying', 'Classifying'),
  extractingEntities('extracting_entities', 'Extracting Clinical Information'),
  normalizing('normalizing', 'Normalizing & Linking Evidence'),
  complete('complete', 'Complete');

  const PipelineStage(this.wire, this.label);

  final String wire;
  final String label;

  static PipelineStage fromWire(Object? raw) {
    final String s = raw?.toString().trim().toLowerCase() ?? '';
    for (final PipelineStage v in PipelineStage.values) {
      if (v.wire == s) return v;
    }
    return PipelineStage.uploaded;
  }
}

/// `FactType`.
enum FactType {
  diagnosis('diagnosis', 'Diagnosis', 'stethoscope'),
  symptom('symptom', 'Symptom', 'activity'),
  medication('medication', 'Medication', 'pill'),
  investigation('investigation', 'Investigation', 'flaskConical'),
  allergy('allergy', 'Allergy', 'alertTriangle'),
  procedure('procedure', 'Procedure', 'syringe'),
  observation('observation', 'Observation', 'eye'),
  other('other', 'Other', 'fileText');

  const FactType(this.wire, this.label, this.icon);

  final String wire;
  final String label;
  final String icon;

  static FactType fromWire(Object? raw) {
    final String s = raw?.toString().trim().toLowerCase() ?? '';
    for (final FactType v in FactType.values) {
      if (v.wire == s) return v;
    }
    return FactType.other;
  }
}

/// `IssueType` — drives the Issues pill tabs.
enum IssueType {
  medicationConflict('medication_conflict', 'Conflicts'),
  dateConflict('date_conflict', 'Date conflicts'),
  duplicateRecord('duplicate_record', 'Duplicates'),
  unclearMedicationStatus('unclear_medication_status', 'Unclear status'),
  diagnosisConflict('diagnosis_conflict', 'Diagnosis conflicts'),
  lowConfidenceFact('low_confidence_fact', 'Low confidence'),
  missingInformation('missing_information', 'Missing information');

  const IssueType(this.wire, this.label);

  final String wire;
  final String label;

  static IssueType fromWire(Object? raw) {
    final String s = raw?.toString().trim().toLowerCase() ?? '';
    for (final IssueType v in IssueType.values) {
      if (v.wire == s) return v;
    }
    return IssueType.lowConfidenceFact;
  }
}

/// `Severity`.
enum Severity {
  low('low', 'Low'),
  medium('medium', 'Medium'),
  high('high', 'High');

  const Severity(this.wire, this.label);

  final String wire;
  final String label;

  static Severity fromWire(Object? raw) {
    final String s = raw?.toString().trim().toLowerCase() ?? '';
    for (final Severity v in Severity.values) {
      if (v.wire == s) return v;
    }
    return Severity.low;
  }
}

/// `Contradiction.status`.
enum IssueStatus {
  open('open', 'Open'),
  acknowledged('acknowledged', 'Acknowledged'),
  resolvedByDoctor('resolved_by_doctor', 'Resolved by doctor'),
  dismissed('dismissed', 'Dismissed');

  const IssueStatus(this.wire, this.label);

  final String wire;
  final String label;

  static IssueStatus fromWire(Object? raw) {
    final String s = raw?.toString().trim().toLowerCase() ?? '';
    for (final IssueStatus v in IssueStatus.values) {
      if (v.wire == s) return v;
    }
    return IssueStatus.open;
  }
}

/// `MedStatus`.
enum MedicationStatus {
  current('current', 'Current'),
  previous('previous', 'Previous'),
  uncertain('uncertain', 'Uncertain');

  const MedicationStatus(this.wire, this.label);

  final String wire;
  final String label;

  static MedicationStatus fromWire(Object? raw) {
    final String s = raw?.toString().trim().toLowerCase() ?? '';
    for (final MedicationStatus v in MedicationStatus.values) {
      if (v.wire == s) return v;
    }
    return MedicationStatus.current;
  }
}

/// `investigations.abnormal_flag`.
enum AbnormalFlag {
  low('low', 'Low'),
  high('high', 'High'),
  normal('normal', 'In range'),
  unknown('unknown', 'Not flagged');

  const AbnormalFlag(this.wire, this.label);

  final String wire;
  final String label;

  bool get isAbnormal => this == low || this == high;

  static AbnormalFlag fromWire(Object? raw) {
    final String s = raw?.toString().trim().toLowerCase() ?? '';
    for (final AbnormalFlag v in AbnormalFlag.values) {
      if (v.wire == s) return v;
    }
    return AbnormalFlag.unknown;
  }
}

/// `timeline_events.event_type`.
enum TimelineEventType {
  medicationStart('medication_start', 'Medication', 'pill'),
  medicationChange('medication_change', 'Dose change', 'replace'),
  investigation('investigation', 'Investigation', 'flaskConical'),
  diagnosis('diagnosis', 'Diagnosis', 'stethoscope'),
  approvedNote('approved_note', 'Approved note', 'badgeCheck'),
  other('other', 'Event', 'dot');

  const TimelineEventType(this.wire, this.label, this.icon);

  final String wire;
  final String label;
  final String icon;

  static TimelineEventType fromWire(Object? raw) {
    final String s = raw?.toString().trim().toLowerCase() ?? '';
    for (final TimelineEventType v in TimelineEventType.values) {
      if (v.wire == s) return v;
    }
    return TimelineEventType.other;
  }
}

/// `ConsultationOrigin`.
enum ConsultationOrigin {
  aiGenerated('ai_generated', 'AI generated'),
  doctorEdited('doctor_edited', 'Doctor edited'),
  approved('approved', 'Approved');

  const ConsultationOrigin(this.wire, this.label);

  final String wire;
  final String label;

  static ConsultationOrigin fromWire(Object? raw) {
    final String s = raw?.toString().trim().toLowerCase() ?? '';
    for (final ConsultationOrigin v in ConsultationOrigin.values) {
      if (v.wire == s) return v;
    }
    return ConsultationOrigin.aiGenerated;
  }
}

/// `Consultation.status`.
enum ConsultationStatus {
  draft('draft', 'Draft'),
  inReview('in_review', 'In review'),
  approved('approved', 'Approved');

  const ConsultationStatus(this.wire, this.label);

  final String wire;
  final String label;

  static ConsultationStatus fromWire(Object? raw) {
    final String s = raw?.toString().trim().toLowerCase() ?? '';
    for (final ConsultationStatus v in ConsultationStatus.values) {
      if (v.wire == s) return v;
    }
    return ConsultationStatus.draft;
  }
}

/// `ClinicalMemory.memory_type`.
enum MemoryType {
  diagnosis('diagnosis', 'Diagnoses'),
  assessment('assessment', 'Assessments'),
  planNote('plan_note', 'Plan notes'),
  medication('medication', 'Medications'),
  allergy('allergy', 'Allergies'),
  history('history', 'History'),
  other('other', 'Other');

  const MemoryType(this.wire, this.label);

  final String wire;
  final String label;

  static MemoryType fromWire(Object? raw) {
    final String s = raw?.toString().trim().toLowerCase() ?? '';
    for (final MemoryType v in MemoryType.values) {
      if (v.wire == s) return v;
    }
    return MemoryType.other;
  }
}

/// `ValidationCheck.severity`.
enum CheckSeverity {
  block('block', 'Must resolve'),
  warn('warn', 'Review'),
  info('info', 'Passed');

  const CheckSeverity(this.wire, this.label);

  final String wire;
  final String label;

  static CheckSeverity fromWire(Object? raw) {
    final String s = raw?.toString().trim().toLowerCase() ?? '';
    for (final CheckSeverity v in CheckSeverity.values) {
      if (v.wire == s) return v;
    }
    return CheckSeverity.info;
  }
}

/// `ValidationOutcome`.
enum ValidationOutcome {
  pass('pass', 'Pass'),
  passWithFlags('pass_with_flags', 'Pass with flags'),
  blocked('blocked', 'Blocked');

  const ValidationOutcome(this.wire, this.label);

  final String wire;
  final String label;

  static ValidationOutcome fromWire(Object? raw) {
    final String s = raw?.toString().trim().toLowerCase() ?? '';
    for (final ValidationOutcome v in ValidationOutcome.values) {
      if (v.wire == s) return v;
    }
    return ValidationOutcome.pass;
  }
}

/// `brief.important_trends[].direction`.
enum TrendDirection {
  up('up', 'Increasing'),
  down('down', 'Decreasing'),
  stable('stable', 'Stable'),
  mixed('mixed', 'Mixed');

  const TrendDirection(this.wire, this.label);

  final String wire;
  final String label;

  static TrendDirection fromWire(Object? raw) {
    final String s = raw?.toString().trim().toLowerCase() ?? '';
    for (final TrendDirection v in TrendDirection.values) {
      if (v.wire == s) return v;
    }
    return TrendDirection.stable;
  }
}

/// Specialties.
///
/// The catalogue itself is fetched from `GET /api/v1/specialties`
/// (`SpecialtyRepository`). This enum exists to (a) parse a wire value back to
/// something with a Lucide glyph and (b) provide an offline mirror of the
/// backend's seed rows, so the picker is never empty and never offers a
/// specialty the backend would reject.
enum Specialty {
  generalMedicine('general_medicine', 'General Medicine', 'stethoscope'),
  diabetology('diabetology', 'Diabetology & Endocrinology', 'droplets'),
  cardiology('cardiology', 'Cardiology', 'heartPulse'),
  orthopedics('orthopedics', 'Orthopedics', 'bone'),
  neurology('neurology', 'Neurology', 'brain'),
  pediatrics('pediatrics', 'Pediatrics', 'baby'),
  other('other', 'Other', 'layers');

  const Specialty(this.wire, this.label, this.icon);

  final String wire;
  final String label;

  /// Name in `AppIcons.table`.
  final String icon;

  static Specialty fromWire(Object? raw) {
    return matching(raw) ?? Specialty.generalMedicine;
  }

  /// The enum value for a wire id, or `null` when the backend offers a
  /// specialty this build has no glyph for.
  static Specialty? matching(Object? raw) {
    final String s = raw?.toString().trim().toLowerCase() ?? '';
    if (s.isEmpty) return null;
    for (final Specialty v in Specialty.values) {
      if (v.wire == s) return v;
    }
    return null;
  }

  /// The default used when nothing has been chosen yet.
  static Specialty get fallback => Specialty.generalMedicine;
}

/// Editable consultation section keys — `ConsultationContent`.
enum ConsultationSection {
  chiefComplaint('chief_complaint', 'Chief complaint', true),
  historyOfPresentIllness(
      'history_of_present_illness', 'History of present illness', true),
  pastHistory('past_history', 'Past history', true),
  currentMedications('current_medications', 'Current medications', false),
  allergies('allergies', 'Allergies', false),
  examination('examination', 'Examination', false),
  investigationsReviewed(
      'investigations_reviewed', 'Investigations reviewed', false),
  assessment('assessment', 'Assessment', false),
  plan('plan', 'Plan', false),
  followUp('follow_up', 'Follow-up', false);

  // ignore: avoid_positional_boolean_parameters — enum values are positional by design.
  const ConsultationSection(this.key, this.label, this.aiPrefilled);

  /// JSON key inside `ConsultationContent`.
  final String key;
  final String label;

  /// True when the AI draft pre-fills this section.
  ///
  /// Plan §9.15: Assessment / Plan / Follow-up start empty so the doctor writes
  /// them. Examination is also left empty by the backend.
  final bool aiPrefilled;

  static ConsultationSection? fromKey(Object? raw) {
    final String? s = raw?.toString();
    for (final ConsultationSection v in ConsultationSection.values) {
      if (v.key == s) return v;
    }
    return null;
  }
}
