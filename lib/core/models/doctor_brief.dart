import '../constants/enums.dart';
import '../utils/confidence_band.dart';
import '../utils/date_format.dart';
import 'json_utils.dart';

/// `POST|GET /patients/{id}/brief` → `DoctorBrief`.
class DoctorBrief {
  const DoctorBrief({
    required this.patientId,
    this.patientName,
    this.patientAge,
    this.specialty = Specialty.generalMedicine,
    this.generatedAt,
    this.chiefComplaint,
    this.relevantHistory = const <BriefHistoryItem>[],
    this.currentMedications = const <BriefMedication>[],
    this.allergies = const <BriefAllergy>[],
    this.recentInvestigations = const <BriefInvestigation>[],
    this.importantTrends = const <BriefTrend>[],
    this.attentionItems = const <BriefAttention>[],
    this.contradictions = const <BriefContradiction>[],
    this.missingInformation = const <BriefMissing>[],
    this.evidenceShortcuts = const <EvidenceShortcut>[],
    this.disclaimer,
  });

  factory DoctorBrief.fromJson(Map<String, dynamic> json) {
    final patient = asMap(json['patient']);
    return DoctorBrief(
      patientId: asStringOr(patient['id'], ''),
      patientName: asString(patient['name']),
      patientAge: asInt(patient['age']),
      specialty: Specialty.fromWire(json['specialty']),
      generatedAt: json['generated_at'],
      chiefComplaint: json['chief_complaint'] == null
          ? null
          : BriefStatement.fromJson(asMap(json['chief_complaint'])),
      relevantHistory: asMapList(json['relevant_history'])
          .map(BriefHistoryItem.fromJson)
          .toList(growable: false),
      currentMedications: asMapList(json['current_medications'])
          .map(BriefMedication.fromJson)
          .toList(growable: false),
      allergies: asMapList(json['allergies'])
          .map(BriefAllergy.fromJson)
          .toList(growable: false),
      recentInvestigations: asMapList(json['recent_investigations'])
          .map(BriefInvestigation.fromJson)
          .toList(growable: false),
      importantTrends: asMapList(json['important_trends'])
          .map(BriefTrend.fromJson)
          .toList(growable: false),
      attentionItems: asMapList(json['attention_items'])
          .map(BriefAttention.fromJson)
          .toList(growable: false),
      contradictions: asMapList(json['contradictions'])
          .map(BriefContradiction.fromJson)
          .toList(growable: false),
      missingInformation: asMapList(json['missing_information'])
          .map(BriefMissing.fromJson)
          .toList(growable: false),
      evidenceShortcuts: asMapList(json['evidence_shortcuts'])
          .map(EvidenceShortcut.fromJson)
          .toList(growable: false),
      disclaimer: asString(json['disclaimer']),
    );
  }

  final String patientId;
  final String? patientName;
  final int? patientAge;
  final Specialty specialty;
  final Object? generatedAt;
  final BriefStatement? chiefComplaint;
  final List<BriefHistoryItem> relevantHistory;
  final List<BriefMedication> currentMedications;
  final List<BriefAllergy> allergies;
  final List<BriefInvestigation> recentInvestigations;
  final List<BriefTrend> importantTrends;
  final List<BriefAttention> attentionItems;
  final List<BriefContradiction> contradictions;
  final List<BriefMissing> missingInformation;
  final List<EvidenceShortcut> evidenceShortcuts;
  final String? disclaimer;

  String get specialtyLabel => specialty.label;
  String get generatedLabel => AppDate.stamp(generatedAt);
  bool get isEmpty =>
      relevantHistory.isEmpty &&
      currentMedications.isEmpty &&
      recentInvestigations.isEmpty &&
      (chiefComplaint?.text.isEmpty ?? true);

  /// Every statement in the brief carries an evidence chip (plan §9.14).
  int get evidenceCount => evidenceShortcuts.length;

  String get disclaimerText =>
      disclaimer ??
      'AI-assisted summary of source records. Not a diagnosis or treatment recommendation.';
}

/// A text + evidence statement (`chief_complaint`, `relevant_history[]`).
class BriefStatement {
  const BriefStatement({
    required this.text,
    this.evidenceIds = const <String>[],
    this.confidenceBand,
  });

  factory BriefStatement.fromJson(Map<String, dynamic> json) {
    return BriefStatement(
      text: asStringOr(json['text'], ''),
      evidenceIds: asStringList(json['evidence_ids']),
      confidenceBand: json['confidence_band'] == null
          ? null
          : ConfidenceBand.fromWire(json['confidence_band']),
    );
  }

  final String text;
  final List<String> evidenceIds;
  final ConfidenceBand? confidenceBand;

  bool get hasText => text.isNotEmpty;
}

class BriefHistoryItem extends BriefStatement {
  const BriefHistoryItem(
      {required super.text, super.evidenceIds, super.confidenceBand});

  factory BriefHistoryItem.fromJson(Map<String, dynamic> json) =>
      BriefHistoryItem.fromBriefStatement(BriefStatement.fromJson(json));

  factory BriefHistoryItem.fromBriefStatement(BriefStatement s) =>
      BriefHistoryItem(
          text: s.text,
          evidenceIds: s.evidenceIds,
          confidenceBand: s.confidenceBand);
}

class BriefMedication {
  const BriefMedication({
    required this.name,
    this.strength,
    this.dose,
    this.frequency,
    this.status,
    this.evidenceIds = const <String>[],
    this.confidenceBand,
    this.conflictFlag = false,
  });

  factory BriefMedication.fromJson(Map<String, dynamic> json) {
    final band = json['confidence_band'];
    return BriefMedication(
      name: asStringOr(json['name'], 'Medication'),
      strength: asString(json['strength']),
      dose: asString(json['dose']),
      frequency: asString(json['frequency']),
      status: asString(json['status']),
      evidenceIds: asStringList(json['evidence_ids']),
      confidenceBand: band == null ? null : ConfidenceBand.fromWire(band),
      conflictFlag: asBool(json['conflict_flag']),
    );
  }

  final String name;
  final String? strength;
  final String? dose;
  final String? frequency;
  final String? status;
  final List<String> evidenceIds;
  final ConfidenceBand? confidenceBand;
  final bool conflictFlag;

  String get doseLine {
    final parts = <String>[
      if ((dose ?? '').isNotEmpty) dose!,
      if ((strength ?? '').isNotEmpty && strength != dose) strength!,
      if ((frequency ?? '').isNotEmpty) frequency!,
    ];
    return parts.isEmpty ? 'Dose not recorded' : parts.join(' · ');
  }
}

class BriefAllergy {
  const BriefAllergy({
    required this.text,
    this.status = 'documented',
    this.evidenceIds = const <String>[],
  });

  factory BriefAllergy.fromJson(Map<String, dynamic> json) {
    return BriefAllergy(
      text: asStringOr(json['text'], ''),
      status: asStringOr(json['status'], 'documented'),
      evidenceIds: asStringList(json['evidence_ids']),
    );
  }

  final String text;
  final String status;
  final List<String> evidenceIds;

  bool get isNotDocumented => status == 'not_documented';
  bool get isEmpty => text.trim().isEmpty || isNotDocumented;
}

class BriefInvestigation {
  const BriefInvestigation({
    required this.test,
    this.value,
    this.unit,
    this.reference,
    this.date,
    this.abnormal = false,
    this.evidenceIds = const <String>[],
  });

  factory BriefInvestigation.fromJson(Map<String, dynamic> json) {
    return BriefInvestigation(
      test: asStringOr(json['test'], 'Investigation'),
      value: asString(json['value']),
      unit: asString(json['unit']),
      reference: asString(json['reference']),
      date: asString(json['date']),
      abnormal: asBool(json['abnormal']),
      evidenceIds: asStringList(json['evidence_ids']),
    );
  }

  final String test;
  final String? value;
  final String? unit;
  final String? reference;
  final String? date;
  final bool abnormal;
  final List<String> evidenceIds;

  String get valueLabel {
    final v = (value ?? '—').trim();
    final u = (unit ?? '').trim();
    return u.isEmpty || v == '—' ? v : '$v $u';
  }
}

class BriefTrend {
  const BriefTrend({
    this.test = 'Trend',
    this.series = const <BriefTrendPoint>[],
    this.direction = TrendDirection.stable,
    this.description,
    this.evidenceIds = const <String>[],
  });

  factory BriefTrend.fromJson(Map<String, dynamic> json) {
    return BriefTrend(
      test: asStringOr(json['test'], 'Trend'),
      // NOTE: the brief uses `val` (not `value`) inside its series.
      series: asMapList(json['series'])
          .map(BriefTrendPoint.fromJson)
          .toList(growable: false),
      direction: TrendDirection.fromWire(json['direction']),
      description: asString(json['description']),
      evidenceIds: asStringList(json['evidence_ids']),
    );
  }

  final String test;
  final List<BriefTrendPoint> series;
  final TrendDirection direction;
  final String? description;
  final List<String> evidenceIds;
}

class BriefTrendPoint {
  const BriefTrendPoint({required this.value, this.dateLabel});

  factory BriefTrendPoint.fromJson(Map<String, dynamic> json) {
    return BriefTrendPoint(
      value: asDoubleOr(json['val'] ?? json['value'], double.nan),
      dateLabel: asString(json['date']),
    );
  }

  final double value;
  final String? dateLabel;

  bool get hasValue => !value.isNaN;
}

class BriefAttention {
  const BriefAttention(
      {required this.text, this.severity, this.evidenceIds = const <String>[]});

  factory BriefAttention.fromJson(Map<String, dynamic> json) {
    return BriefAttention(
      text: asStringOr(json['text'], ''),
      severity:
          json['severity'] == null ? null : Severity.fromWire(json['severity']),
      evidenceIds: asStringList(json['evidence_ids']),
    );
  }

  final String text;
  final Severity? severity;
  final List<String> evidenceIds;
}

class BriefContradiction {
  const BriefContradiction(
      {this.issueId, this.text = '', this.sources = const <String>[]});

  factory BriefContradiction.fromJson(Map<String, dynamic> json) {
    return BriefContradiction(
      issueId: asString(json['issue_id']),
      text: asStringOr(json['text'], ''),
      sources: asStringList(json['sources']),
    );
  }

  final String? issueId;
  final String text;
  final List<String> sources;
}

class BriefMissing {
  const BriefMissing({required this.prompt, this.reason});

  factory BriefMissing.fromJson(Map<String, dynamic> json) {
    return BriefMissing(
      prompt: asStringOr(json['prompt'], ''),
      reason: asString(json['reason']),
    );
  }

  final String prompt;
  final String? reason;
}

class EvidenceShortcut {
  const EvidenceShortcut({
    required this.evidenceId,
    required this.label,
    this.documentId,
    this.page,
  });

  factory EvidenceShortcut.fromJson(Map<String, dynamic> json) {
    return EvidenceShortcut(
      evidenceId: asStringOr(json['evidence_id'], ''),
      label: asStringOr(json['label'], 'Source'),
      documentId: asString(json['document_id']),
      page: asInt(json['page']),
    );
  }

  final String evidenceId;
  final String label;
  final String? documentId;
  final int? page;
}
