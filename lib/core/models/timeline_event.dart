import '../constants/enums.dart';
import 'json_utils.dart';

/// One row of `GET /patients/{id}/timeline`.
class TimelineEvent {
  const TimelineEvent({
    required this.id,
    required this.title,
    this.eventType = TimelineEventType.other,
    this.eventDate,
    this.datePrecision = 'day',
    this.summary,
    this.relatedFactIds = const <String>[],
    this.sourceDocumentId,
    this.sortKey,
    this.createdAt,
  });

  factory TimelineEvent.fromJson(Map<String, dynamic> json) {
    return TimelineEvent(
      id: asStringOr(json['id'], ''),
      title: asStringOr(json['title'], 'Clinical event'),
      eventType: TimelineEventType.fromWire(json['event_type']),
      eventDate: json['event_date'],
      datePrecision: asStringOr(json['date_precision'], 'day'),
      summary: asString(json['summary']),
      relatedFactIds: asStringList(json['related_fact_ids']),
      sourceDocumentId: asString(json['source_document_id']),
      sortKey: asString(json['sort_key']),
      createdAt: json['created_at'],
    );
  }

  final String id;
  final String title;
  final TimelineEventType eventType;
  final Object? eventDate;
  final String datePrecision;
  final String? summary;
  final List<String> relatedFactIds;
  final String? sourceDocumentId;
  final String? sortKey;
  final Object? createdAt;

  bool get isUndated => eventDate == null || eventDate.toString().isEmpty;
}

/// One row of `GET /patients/{id}/issues` (the `contradictions` table).
class ClinicalIssue {
  const ClinicalIssue({
    required this.id,
    required this.title,
    required this.issueType,
    this.severity = Severity.low,
    this.description,
    this.relatedDocumentIds = const <String>[],
    this.relatedFactIds = const <String>[],
    this.detail = const <String, dynamic>{},
    this.status = IssueStatus.open,
    this.doctorNote,
    this.createdAt,
    this.updatedAt,
  });

  factory ClinicalIssue.fromJson(Map<String, dynamic> json) {
    return ClinicalIssue(
      id: asStringOr(json['id'], ''),
      title: asStringOr(json['title'], 'Needs review'),
      issueType: IssueType.fromWire(json['issue_type']),
      severity: Severity.fromWire(json['severity']),
      description: asString(json['description']),
      relatedDocumentIds: asStringList(json['related_document_ids']),
      relatedFactIds: asStringList(json['related_fact_ids']),
      detail: asMap(json['detail_json']),
      status: IssueStatus.fromWire(json['status']),
      doctorNote: asString(json['doctor_note']),
      createdAt: json['created_at'],
      updatedAt: json['updated_at'],
    );
  }

  final String id;
  final String title;
  final IssueType issueType;
  final Severity severity;
  final String? description;
  final List<String> relatedDocumentIds;
  final List<String> relatedFactIds;
  final Map<String, dynamic> detail;
  final IssueStatus status;
  final String? doctorNote;
  final Object? createdAt;
  final Object? updatedAt;

  bool get isOpen => status == IssueStatus.open;
  bool get isMissingInfo => issueType == IssueType.missingInformation;
  bool get isConflict =>
      issueType == IssueType.medicationConflict ||
      issueType == IssueType.diagnosisConflict ||
      issueType == IssueType.dateConflict;

  /// `Potentially missing: …` phrasing — plan §6.6 rule 4.
  String get prompt => asString(detail['prompt']) ?? title;

  String get reason => asString(detail['reason']) ?? '';

  /// The drug a medication conflict is about, when the backend supplies it.
  String? get drug {
    final d = asString(detail['drug']);
    if (d != null) return d;
    // Older rows use a different key; stay tolerant rather than assuming.
    for (final key in const <String>[
      'canonical_name',
      'drug_name',
      'medication'
    ]) {
      final v = asString(detail[key]);
      if (v != null) return v;
    }
    return null;
  }

  /// The two records named in a conflict, shown side by side (plan §6.6 rule 3).
  ///
  /// Preferred source is `detail_json.source_1` / `source_2`, which the backend
  /// fills with `{doc, dose, freq}` — structured and unambiguous. When the
  /// detail block is missing or empty the description is split on `" vs "`
  /// instead. Neither branch ever reorders or judges the two sides.
  List<String> get sourceLines {
    final List<String> structured = <String>[];
    for (final String key in const <String>['source_1', 'source_2']) {
      final String? line = _describeConflictSource(asMap(detail[key]));
      if (line != null) structured.add(line);
    }
    if (structured.length >= 2) return structured;

    final String? d = description;
    if (d == null) return const <String>[];
    final String tail = d.split(':').last;
    return tail
        .split(' vs ')
        .map(_trimSentence)
        .where((String s) => s.isNotEmpty)
        .toList(growable: false);
  }

  /// Drops the sentence-terminating full stop from a split clause so the two
  /// sides read as fragments, not as one of them ending the sentence.
  static String _trimSentence(String value) {
    String s = value.trim();
    while (s.endsWith('.') || s.endsWith(',')) {
      s = s.substring(0, s.length - 1).trimRight();
    }
    return s;
  }

  /// `{doc, dose, freq}` → one readable line. Returns null when nothing usable.
  static String? _describeConflictSource(Map<String, dynamic> source) {
    if (source.isEmpty) return null;
    final List<String> parts = <String>[
      if ((asString(source['dose']) ?? '').isNotEmpty) asString(source['dose'])!,
      if ((asString(source['freq']) ?? '').isNotEmpty) asString(source['freq'])!,
      if ((asString(source['doc']) ?? '').isNotEmpty) asString(source['doc'])!,
    ];
    return parts.isEmpty ? null : parts.join(' · ');
  }
}

/// Result of `PATCH /issues/{id}`.
class IssuePatchResult {
  const IssuePatchResult({
    required this.id,
    required this.status,
    this.title,
    this.severity,
    this.doctorNote,
  });

  factory IssuePatchResult.fromJson(Map<String, dynamic> json) {
    return IssuePatchResult(
      id: asStringOr(json['id'], ''),
      status: IssueStatus.fromWire(json['status']),
      title: asString(json['title']),
      severity:
          json['severity'] == null ? null : Severity.fromWire(json['severity']),
      doctorNote: asString(json['doctor_note']),
    );
  }

  final String id;
  final IssueStatus status;
  final String? title;
  final Severity? severity;
  final String? doctorNote;
}
