import '../constants/enums.dart';
import '../utils/date_format.dart';
import 'json_utils.dart';

/// `ConsultationContent` — the editable document body.
class ConsultationContent {
  ConsultationContent({
    this.chiefComplaint = '',
    this.historyOfPresentIllness = '',
    this.pastHistory = '',
    List<ConsultationMedicationRow> currentMedications =
        const <ConsultationMedicationRow>[],
    List<ConsultationAllergyRow> allergies = const <ConsultationAllergyRow>[],
    this.examination = '',
    List<ConsultationInvestigationRow> investigationsReviewed =
        const <ConsultationInvestigationRow>[],
    this.assessment = '',
    this.plan = '',
    this.followUp = '',
    List<ConsultationFlag> flags = const <ConsultationFlag>[],
    List<String> evidenceIds = const <String>[],
  })  : currentMedications =
            List<ConsultationMedicationRow>.from(currentMedications),
        allergies = List<ConsultationAllergyRow>.from(allergies),
        investigationsReviewed =
            List<ConsultationInvestigationRow>.from(investigationsReviewed),
        flags = List<ConsultationFlag>.from(flags),
        evidenceIds = List<String>.from(evidenceIds);

  factory ConsultationContent.fromJson(Map<String, dynamic> json) {
    return ConsultationContent(
      chiefComplaint: asStringOr(json['chief_complaint'], ''),
      historyOfPresentIllness:
          asStringOr(json['history_of_present_illness'], ''),
      pastHistory: asStringOr(json['past_history'], ''),
      currentMedications: asMapList(json['current_medications'])
          .map(ConsultationMedicationRow.fromJson)
          .toList(),
      allergies: asMapList(json['allergies'])
          .map(ConsultationAllergyRow.fromJson)
          .toList(),
      examination: asStringOr(json['examination'], ''),
      investigationsReviewed: asMapList(json['investigations_reviewed'])
          .map(ConsultationInvestigationRow.fromJson)
          .toList(),
      assessment: asStringOr(json['assessment'], ''),
      plan: asStringOr(json['plan'], ''),
      followUp: asStringOr(json['follow_up'], ''),
      flags: asMapList(json['flags']).map(ConsultationFlag.fromJson).toList(),
      evidenceIds: asStringList(json['evidence_ids']),
    );
  }

  String chiefComplaint;
  String historyOfPresentIllness;
  String pastHistory;
  List<ConsultationMedicationRow> currentMedications;
  List<ConsultationAllergyRow> allergies;
  String examination;
  List<ConsultationInvestigationRow> investigationsReviewed;
  String assessment;
  String plan;
  String followUp;
  List<ConsultationFlag> flags;
  List<String> evidenceIds;

  /// Read a text section by its enum key.
  String textFor(ConsultationSection section) => switch (section) {
        ConsultationSection.chiefComplaint => chiefComplaint,
        ConsultationSection.historyOfPresentIllness => historyOfPresentIllness,
        ConsultationSection.pastHistory => pastHistory,
        ConsultationSection.examination => examination,
        ConsultationSection.assessment => assessment,
        ConsultationSection.plan => plan,
        ConsultationSection.followUp => followUp,
        ConsultationSection.currentMedications => _rowsToText(currentMedications
            .map((ConsultationMedicationRow m) =>
                '${m.name}${m.dose.isEmpty ? '' : ' ${m.dose}'}${m.freq.isEmpty ? '' : ' · ${m.freq}'}')
            .toList()),
        ConsultationSection.allergies => _rowsToText(
            allergies.map((ConsultationAllergyRow a) => a.text).toList(),
          ),
        ConsultationSection.investigationsReviewed => _rowsToText(
            investigationsReviewed
                .map((ConsultationInvestigationRow i) =>
                    '${i.test}: ${i.val}${i.unit.isEmpty ? '' : ' ${i.unit}'}')
                .toList(),
          ),
      };

  void setText(ConsultationSection section, String value) {
    switch (section) {
      case ConsultationSection.chiefComplaint:
        chiefComplaint = value;
      case ConsultationSection.historyOfPresentIllness:
        historyOfPresentIllness = value;
      case ConsultationSection.pastHistory:
        pastHistory = value;
      case ConsultationSection.examination:
        examination = value;
      case ConsultationSection.assessment:
        assessment = value;
      case ConsultationSection.plan:
        plan = value;
      case ConsultationSection.followUp:
        followUp = value;
      case ConsultationSection.currentMedications:
      case ConsultationSection.allergies:
      case ConsultationSection.investigationsReviewed:
        break;
    }
  }

  bool get isEmpty =>
      chiefComplaint.trim().isEmpty &&
      historyOfPresentIllness.trim().isEmpty &&
      pastHistory.trim().isEmpty &&
      examination.trim().isEmpty &&
      assessment.trim().isEmpty &&
      plan.trim().isEmpty &&
      followUp.trim().isEmpty &&
      currentMedications.isEmpty &&
      allergies.isEmpty &&
      investigationsReviewed.isEmpty;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'chief_complaint': chiefComplaint,
        'history_of_present_illness': historyOfPresentIllness,
        'past_history': pastHistory,
        'current_medications': currentMedications
            .map((ConsultationMedicationRow m) => m.toJson())
            .toList(),
        'allergies':
            allergies.map((ConsultationAllergyRow a) => a.toJson()).toList(),
        'examination': examination,
        'investigations_reviewed': investigationsReviewed
            .map((ConsultationInvestigationRow i) => i.toJson())
            .toList(),
        'assessment': assessment,
        'plan': plan,
        'follow_up': followUp,
        'flags': flags.map((ConsultationFlag f) => f.toJson()).toList(),
        'evidence_ids': evidenceIds,
      };

  ConsultationContent copy() => ConsultationContent.fromJson(toJson());

  static String _rowsToText(List<String> rows) =>
      rows.where((String r) => r.trim().isNotEmpty).join('\n');
}

class ConsultationMedicationRow {
  const ConsultationMedicationRow(
      {required this.name, this.dose = '', this.freq = '', this.factId});

  factory ConsultationMedicationRow.fromJson(Map<String, dynamic> json) {
    return ConsultationMedicationRow(
      name: asStringOr(json['name'], 'Medication'),
      dose: asStringOr(json['dose'], ''),
      freq: asStringOr(json['freq'] ?? json['frequency'], ''),
      factId: asString(json['fact_id']),
    );
  }

  final String name;
  final String dose;
  final String freq;
  final String? factId;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'name': name,
        'dose': dose,
        'freq': freq,
        if (factId != null) 'fact_id': factId,
      };
}

class ConsultationAllergyRow {
  const ConsultationAllergyRow({required this.text, this.factId});

  factory ConsultationAllergyRow.fromJson(Map<String, dynamic> json) {
    return ConsultationAllergyRow(
      text: asStringOr(json['text'], ''),
      factId: asString(json['fact_id']),
    );
  }

  final String text;
  final String? factId;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'text': text,
        if (factId != null) 'fact_id': factId,
      };
}

class ConsultationInvestigationRow {
  const ConsultationInvestigationRow(
      {required this.test, required this.val, this.unit = '', this.factId});

  factory ConsultationInvestigationRow.fromJson(Map<String, dynamic> json) {
    return ConsultationInvestigationRow(
      test: asStringOr(json['test'], 'Investigation'),
      val: asStringOr(json['val'] ?? json['value'], ''),
      unit: asStringOr(json['unit'], ''),
      factId: asString(json['fact_id']),
    );
  }

  final String test;
  final String val;
  final String unit;
  final String? factId;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'test': test,
        'val': val,
        'unit': unit,
        if (factId != null) 'fact_id': factId,
      };
}

class ConsultationFlag {
  const ConsultationFlag({required this.text, this.by});

  factory ConsultationFlag.fromJson(Map<String, dynamic> json) {
    return ConsultationFlag(
      text: asStringOr(json['text'], ''),
      by: asString(json['by']),
    );
  }

  final String text;
  final String? by;

  Map<String, dynamic> toJson() => <String, dynamic>{'text': text, 'by': by};
}

/// One `ConsultationVersion`.
class ConsultationVersion {
  const ConsultationVersion({
    required this.id,
    required this.versionNumber,
    required this.origin,
    this.changeSummary,
    this.editedBy,
    this.createdAt,
    this.content,
  });

  factory ConsultationVersion.fromJson(Map<String, dynamic> json) {
    return ConsultationVersion(
      id: asStringOr(json['id'], ''),
      versionNumber: asIntOr(json['version_number'] ?? json['version'], 1),
      origin: ConsultationOrigin.fromWire(json['origin']),
      changeSummary: asString(json['change_summary']),
      editedBy: asString(json['edited_by']),
      createdAt: json['created_at'],
      content: json['content'] == null
          ? null
          : ConsultationContent.fromJson(asMap(json['content'])),
    );
  }

  final String id;
  final int versionNumber;
  final ConsultationOrigin origin;
  final String? changeSummary;
  final String? editedBy;
  final Object? createdAt;
  final ConsultationContent? content;

  String get label => 'v$versionNumber · ${origin.label}';
  String get stampLabel => AppDate.stamp(createdAt);
}

/// `Consultation` (with `current_version` embedded on GET/POST).
class Consultation {
  const Consultation({
    required this.id,
    required this.patientId,
    this.specialty = Specialty.generalMedicine,
    this.status = ConsultationStatus.draft,
    this.currentVersionId,
    this.approvedAt,
    this.approvedBy,
    this.currentVersion,
  });

  factory Consultation.fromJson(Map<String, dynamic> json) {
    return Consultation(
      id: asStringOr(json['id'], ''),
      patientId: asStringOr(json['patient_id'], ''),
      specialty: Specialty.fromWire(json['specialty']),
      status: ConsultationStatus.fromWire(json['status']),
      currentVersionId: asString(json['current_version_id']),
      approvedAt: json['approved_at'],
      approvedBy: asString(json['approved_by']),
      currentVersion: json['current_version'] == null
          ? null
          : ConsultationVersion.fromJson(asMap(json['current_version'])),
    );
  }

  final String id;
  final String patientId;
  final Specialty specialty;
  final ConsultationStatus status;
  final String? currentVersionId;
  final Object? approvedAt;
  final String? approvedBy;
  final ConsultationVersion? currentVersion;

  bool get isApproved => status == ConsultationStatus.approved;
  bool get isLocked => isApproved;

  String get versionChipLabel {
    final v = currentVersion;
    if (v == null) return 'Draft';
    return 'v${v.versionNumber} · ${v.origin.label}';
  }
}

/// One entry of `POST /consultations/{id}/approve/preview` → `checks[]`.
class ApprovalCheck {
  const ApprovalCheck({
    required this.name,
    required this.passed,
    required this.severity,
    required this.detail,
  });

  factory ApprovalCheck.fromJson(Map<String, dynamic> json) {
    return ApprovalCheck(
      name: asStringOr(json['name'], 'check'),
      passed: asBool(json['passed']),
      severity: CheckSeverity.fromWire(json['severity']),
      detail: asStringOr(json['detail'], ''),
    );
  }

  final String name;
  final bool passed;
  final CheckSeverity severity;
  final String detail;

  /// Doctor-facing label for the machine check name.
  String get label => _labels[name] ?? _humanise(name);

  static const Map<String, String> _labels = <String, String>{
    'authorship_state_check': 'Untouched AI draft',
    'unacknowledged_high_conflict': 'Open high-severity conflicts',
    'open_medium_conflict': 'Open medium-severity conflicts',
    'directive_language': 'Directive language',
    'causality_language': 'Causal claims',
    'provenance_check': 'Provenance citations',
    'llm_judge_faithfulness': 'Source faithfulness',
    'conflict_integrity': 'Conflict integrity',
    'hallucination_check': 'Hallucination check',
    'numeric_consistency': 'Numeric consistency',
    'completeness_allergies': 'Allergy completeness',
    'llm_judge_score': 'Judge score',
  };

  static String _humanise(String raw) {
    final words = raw.replaceAll(RegExp(r'[_\-]+'), ' ').trim();
    if (words.isEmpty) return raw;
    return '${words[0].toUpperCase()}${words.substring(1)}';
  }
}

/// One entry of `proposed_memory_items[]`.
class ProposedMemoryItem {
  const ProposedMemoryItem({required this.type, required this.value});

  factory ProposedMemoryItem.fromJson(Map<String, dynamic> json) {
    return ProposedMemoryItem(
      type: MemoryType.fromWire(json['type']),
      value: asStringOr(json['value'], ''),
    );
  }

  final MemoryType type;
  final String value;
}

/// `POST /consultations/{id}/approve/preview`.
class ApprovalPreview {
  const ApprovalPreview({
    required this.outcome,
    required this.canApprove,
    this.checks = const <ApprovalCheck>[],
    this.proposedMemoryItems = const <ProposedMemoryItem>[],
  });

  factory ApprovalPreview.fromJson(Map<String, dynamic> json) {
    return ApprovalPreview(
      outcome: ValidationOutcome.fromWire(json['outcome']),
      canApprove: asBool(json['can_approve']),
      checks: asMapList(json['checks'])
          .map(ApprovalCheck.fromJson)
          .toList(growable: false),
      proposedMemoryItems: asMapList(json['proposed_memory_items'])
          .map(ProposedMemoryItem.fromJson)
          .toList(growable: false),
    );
  }

  final ValidationOutcome outcome;
  final bool canApprove;
  final List<ApprovalCheck> checks;
  final List<ProposedMemoryItem> proposedMemoryItems;

  List<ApprovalCheck> get blockers => checks
      .where(
          (ApprovalCheck c) => !c.passed && c.severity == CheckSeverity.block)
      .toList(growable: false);

  List<ApprovalCheck> get warnings => checks
      .where((ApprovalCheck c) => !c.passed && c.severity == CheckSeverity.warn)
      .toList(growable: false);

  List<ApprovalCheck> get passed =>
      checks.where((ApprovalCheck c) => c.passed).toList(growable: false);

  /// Required acknowledgements the doctor must tick before the CTA enables.
  int get requiredAcknowledgements => blockers.length + warnings.length;

  bool canApproveWith({required bool acknowledged}) =>
      canApprove && (requiredAcknowledgements == 0 || acknowledged);
}

/// `POST /consultations/{id}/approve` result.
class ApprovalResult {
  const ApprovalResult({
    required this.consultationId,
    required this.status,
    this.approvedAt,
    this.approvedBy,
    this.memoryItemsCreated = 0,
    this.reportId,
    this.validationFlags = const <String>[],
  });

  factory ApprovalResult.fromJson(Map<String, dynamic> json) {
    return ApprovalResult(
      consultationId: asStringOr(json['consultation_id'] ?? json['id'], ''),
      status: ConsultationStatus.fromWire(json['status']),
      approvedAt: json['approved_at'],
      approvedBy: asString(json['approved_by']),
      memoryItemsCreated: asIntOr(json['memory_items_created'], 0),
      reportId: asString(json['report_id']),
      validationFlags: asStringList(json['validation_flags']),
    );
  }

  final String consultationId;
  final ConsultationStatus status;
  final Object? approvedAt;
  final String? approvedBy;
  final int memoryItemsCreated;
  final String? reportId;
  final List<String> validationFlags;
}
