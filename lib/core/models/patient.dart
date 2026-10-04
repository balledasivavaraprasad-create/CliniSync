import '../constants/enums.dart';
import '../utils/date_format.dart';
import 'json_utils.dart';

/// `PatientResponse`.
class Patient {
  const Patient({
    required this.id,
    required this.fullName,
    this.dateOfBirth,
    this.ageYears,
    this.sex,
    this.contactRef,
    this.isDemo = false,
    this.lastActivityAt,
    this.createdAt,
  });

  factory Patient.fromJson(Map<String, dynamic> json) {
    return Patient(
      id: asStringOr(json['id'], ''),
      fullName: asStringOr(json['full_name'], 'Unnamed patient'),
      dateOfBirth: json['date_of_birth'],
      ageYears: asInt(json['age_years']),
      sex: asString(json['sex']),
      contactRef: asString(json['contact_ref']),
      isDemo: asBool(json['is_demo']),
      lastActivityAt: json['last_activity_at'],
      createdAt: json['created_at'],
    );
  }

  final String id;
  final String fullName;

  /// Free-text on the backend (`"1984-03-22"`, `"1984"`, `"03/2022"`).
  final Object? dateOfBirth;
  final int? ageYears;
  final String? sex;
  final String? contactRef;
  final bool isDemo;
  final Object? lastActivityAt;
  final Object? createdAt;

  int? get age => AppDate.age(ageYears: ageYears, dateOfBirth: dateOfBirth);

  String get ageLabel =>
      AppDate.ageLabel(ageYears: ageYears, dateOfBirth: dateOfBirth);

  String get lastSeenLabel => AppDate.relative(lastActivityAt);

  /// `54 yrs • Diabetology` style subtitle seed.
  String get sexLabel {
    final s = sex?.toLowerCase();
    return switch (s) {
      'male' || 'm' => 'Male',
      'female' || 'f' => 'Female',
      'other' || 'o' => 'Other',
      _ => 'Sex not recorded',
    };
  }

  /// Serif monogram used on patient cards and rows (plan §6.5 — no photos).
  String get monogram {
    final parts = fullName
        .trim()
        .split(RegExp(r'\s+'))
        .where((p) => p.isNotEmpty)
        .toList();
    if (parts.isEmpty) return '?';
    if (parts.length == 1) {
      return parts.first
          .substring(0, parts.first.length >= 2 ? 2 : 1)
          .toUpperCase();
    }
    return '${parts.first[0]}${parts.last[0]}'.toUpperCase();
  }

  Map<String, dynamic> toJson() => <String, dynamic>{
        'id': id,
        'full_name': fullName,
        'date_of_birth': dateOfBirth,
        'age_years': ageYears,
        'sex': sex,
        'contact_ref': contactRef,
        'is_demo': isDemo,
        'last_activity_at': lastActivityAt,
        'created_at': createdAt,
      };
}

/// Body of `POST /api/v1/patients` (`PatientCreate`).
class PatientCreate {
  const PatientCreate({
    required this.fullName,
    this.dateOfBirth,
    this.ageYears,
    this.sex,
    this.contactRef,
    this.isDemo = false,
  });

  final String fullName;
  final String? dateOfBirth;
  final int? ageYears;
  final String? sex;
  final String? contactRef;
  final bool isDemo;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'full_name': fullName,
        if (dateOfBirth != null && dateOfBirth!.isNotEmpty)
          'date_of_birth': dateOfBirth,
        if (ageYears != null) 'age_years': ageYears,
        if (sex != null && sex!.isNotEmpty) 'sex': sex,
        if (contactRef != null && contactRef!.isNotEmpty)
          'contact_ref': contactRef,
        'is_demo': isDemo,
      };
}

/// One entry of `overview.attention_items`.
class AttentionItem {
  const AttentionItem({
    required this.id,
    required this.title,
    this.description,
    this.severity = Severity.low,
    this.issueType = IssueType.lowConfidenceFact,
  });

  factory AttentionItem.fromJson(Map<String, dynamic> json) {
    return AttentionItem(
      id: asStringOr(json['id'], ''),
      title: asStringOr(json['title'], 'Needs review'),
      description: asString(json['description']),
      severity: Severity.fromWire(json['severity']),
      issueType: IssueType.fromWire(json['issue_type']),
    );
  }

  final String id;
  final String title;
  final String? description;
  final Severity severity;
  final IssueType issueType;
}

/// One entry of `overview.timeline_preview`.
class TimelinePreviewItem {
  const TimelinePreviewItem({
    required this.id,
    required this.title,
    this.eventDate,
    this.eventType = TimelineEventType.other,
    this.summary,
  });

  factory TimelinePreviewItem.fromJson(Map<String, dynamic> json) {
    return TimelinePreviewItem(
      id: asStringOr(json['id'], ''),
      title: asStringOr(json['title'], 'Event'),
      eventDate: json['event_date'],
      eventType: TimelineEventType.fromWire(json['event_type']),
      summary: asString(json['summary']),
    );
  }

  final String id;
  final String title;
  final Object? eventDate;
  final TimelineEventType eventType;
  final String? summary;
}

/// One entry of `overview.current_medications`.
class MedicationPreview {
  const MedicationPreview({
    required this.id,
    required this.canonicalName,
    this.rawName,
    this.doseText,
    this.frequencyText,
    this.status = MedicationStatus.current,
  });

  factory MedicationPreview.fromJson(Map<String, dynamic> json) {
    return MedicationPreview(
      id: asStringOr(json['id'], ''),
      canonicalName: asStringOr(json['canonical_name'], 'Medication'),
      rawName: asString(json['raw_name']),
      doseText: asString(json['dose_text']),
      frequencyText: asString(json['frequency_text']),
      status: MedicationStatus.fromWire(json['status']),
    );
  }

  final String id;
  final String canonicalName;
  final String? rawName;
  final String? doseText;
  final String? frequencyText;
  final MedicationStatus status;

  String get displayName => _titleCase(canonicalName);
}

/// One entry of `overview.latest_investigations`.
class InvestigationPreview {
  const InvestigationPreview({
    required this.id,
    required this.testName,
    this.valueText,
    this.unit,
    this.abnormalFlag = AbnormalFlag.unknown,
    this.observedDate,
  });

  factory InvestigationPreview.fromJson(Map<String, dynamic> json) {
    return InvestigationPreview(
      id: asStringOr(json['id'], ''),
      testName: asStringOr(json['test_name_canonical'], 'Investigation'),
      valueText: asString(json['value_text']),
      unit: asString(json['unit']),
      abnormalFlag: AbnormalFlag.fromWire(json['abnormal_flag']),
      observedDate: json['observed_date'],
    );
  }

  final String id;
  final String testName;
  final String? valueText;
  final String? unit;
  final AbnormalFlag abnormalFlag;
  final Object? observedDate;
}

/// One entry of `overview.memory_summary`.
class MemoryPreviewItem {
  const MemoryPreviewItem({
    required this.id,
    required this.memoryType,
    required this.content,
    this.createdAt,
  });

  factory MemoryPreviewItem.fromJson(Map<String, dynamic> json) {
    return MemoryPreviewItem(
      id: asStringOr(json['id'], ''),
      memoryType: MemoryType.fromWire(json['memory_type']),
      content: asStringOr(json['content'], '') == ''
          ? ''
          : _flatten(json['content']),
      createdAt: json['created_at'],
    );
  }

  final String id;
  final MemoryType memoryType;
  final String content;
  final Object? createdAt;
}

/// `GET /api/v1/patients/{id}/overview` aggregate.
class PatientOverview {
  const PatientOverview({
    required this.patient,
    required this.sourceCount,
    this.latestBrief,
    this.attentionItems = const <AttentionItem>[],
    this.timelinePreview = const <TimelinePreviewItem>[],
    this.currentMedications = const <MedicationPreview>[],
    this.latestInvestigations = const <InvestigationPreview>[],
    this.memorySummary = const <MemoryPreviewItem>[],
    this.openIssueCounts = const <String, int>{},
  });

  factory PatientOverview.fromJson(Map<String, dynamic> json) {
    return PatientOverview(
      patient: Patient.fromJson(asMap(json['patient'])),
      sourceCount: asIntOr(json['source_count'], 0),
      latestBrief:
          json['latest_brief'] == null ? null : asMap(json['latest_brief']),
      attentionItems: asMapList(json['attention_items'])
          .map(AttentionItem.fromJson)
          .toList(growable: false),
      timelinePreview: asMapList(json['timeline_preview'])
          .map(TimelinePreviewItem.fromJson)
          .toList(growable: false),
      currentMedications: asMapList(json['current_medications'])
          .map(MedicationPreview.fromJson)
          .toList(growable: false),
      latestInvestigations: asMapList(json['latest_investigations'])
          .map(InvestigationPreview.fromJson)
          .toList(growable: false),
      memorySummary: asMapList(json['memory_summary'])
          .map(MemoryPreviewItem.fromJson)
          .toList(growable: false),
      openIssueCounts: _counts(json['open_issue_counts']),
    );
  }

  final Patient patient;
  final int sourceCount;
  final Map<String, dynamic>? latestBrief;
  final List<AttentionItem> attentionItems;
  final List<TimelinePreviewItem> timelinePreview;
  final List<MedicationPreview> currentMedications;
  final List<InvestigationPreview> latestInvestigations;
  final List<MemoryPreviewItem> memorySummary;
  final Map<String, int> openIssueCounts;

  int get openIssueTotal =>
      openIssueCounts.values.fold(0, (int a, int b) => a + b);

  int get highSeverityOpen => attentionItems
      .where((AttentionItem i) => i.severity == Severity.high)
      .length;

  bool get hasClinicalFacts =>
      sourceCount > 0 || latestInvestigations.isNotEmpty;

  static Map<String, int> _counts(Object? raw) {
    final map = asMap(raw);
    final out = <String, int>{};
    map.forEach((String k, dynamic v) {
      final n = asInt(v);
      if (n != null && n > 0) out[k] = n;
    });
    return out;
  }
}

/// `medication_conflict` + `missing_information` counts used by the stat strip.
extension OverviewStats on PatientOverview {
  int get conflictCount =>
      openIssueCounts[IssueType.medicationConflict.wire] ??
      openIssueCounts[IssueType.diagnosisConflict.wire] ??
      openIssueCounts[IssueType.dateConflict.wire] ??
      0;

  int get missingCount =>
      openIssueCounts[IssueType.missingInformation.wire] ??
      openIssueCounts[IssueType.unclearMedicationStatus.wire] ??
      0;
}

String _titleCase(String value) {
  if (value.isEmpty) return value;
  return value
      .split(RegExp(r'[\s_\-]+'))
      .where((String p) => p.isNotEmpty)
      .map((String p) => '${p[0].toUpperCase()}${p.substring(1)}')
      .join(' ');
}

/// Flattens a nested JSON content map into a single readable line.
String _flatten(Object? raw) {
  final map = asMap(raw);
  if (map.isEmpty) return '';
  return map.entries.map((MapEntry<String, dynamic> e) {
    final v = e.value;
    if (v is List) {
      return '${e.key}: ${v.map((dynamic x) => x.toString()).join(', ')}';
    }
    return '${e.key}: ${v.toString()}';
  }).join(' · ');
}
