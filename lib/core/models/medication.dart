import '../constants/enums.dart';
import '../utils/confidence_band.dart';
import 'json_utils.dart';

/// One row of `GET /patients/{id}/medications`.
class Medication {
  const Medication({
    required this.id,
    required this.canonicalName,
    this.rawName,
    this.strengthValue,
    this.strengthUnit,
    this.doseText,
    this.frequencyCode,
    this.frequencyText,
    this.route,
    this.durationText,
    this.status = MedicationStatus.current,
    this.statusReason,
    this.confidence,
    this.confidenceBand = ConfidenceBand.needsVerification,
    this.sourceDocumentId,
    this.conflictIds = const <String>[],
    this.hasConflict = false,
    this.historyCount = 0,
  });

  factory Medication.fromJson(Map<String, dynamic> json) {
    final confidence = asDouble(json['confidence']);
    return Medication(
      id: asStringOr(json['id'], ''),
      canonicalName: asStringOr(json['canonical_name'], 'Medication'),
      rawName: asString(json['raw_name']),
      strengthValue: asDouble(json['strength_value']),
      strengthUnit: asString(json['strength_unit']),
      doseText: asString(json['dose_text']),
      frequencyCode: asString(json['frequency_code']),
      frequencyText: asString(json['frequency_text']),
      route: asString(json['route']),
      durationText: asString(json['duration_text']),
      status: MedicationStatus.fromWire(json['status']),
      statusReason: asString(json['status_reason']),
      confidence: confidence,
      confidenceBand: ConfidenceBand.fromWire(json['confidence_band'],
          confidence: confidence),
      sourceDocumentId: asString(json['source_document_id']),
      conflictIds: asStringList(json['conflict_ids']),
      hasConflict: asBool(json['has_conflict']) ||
          asList(json['conflict_ids']).isNotEmpty,
      historyCount: asIntOr(json['history_count'], 0),
    );
  }

  final String id;
  final String canonicalName;
  final String? rawName;
  final double? strengthValue;
  final String? strengthUnit;
  final String? doseText;
  final String? frequencyCode;
  final String? frequencyText;
  final String? route;
  final String? durationText;
  final MedicationStatus status;
  final String? statusReason;
  final double? confidence;
  final ConfidenceBand confidenceBand;
  final String? sourceDocumentId;
  final List<String> conflictIds;
  final bool hasConflict;
  final int historyCount;

  String get displayName => _titleCase(canonicalName);

  /// `500 mg · twice daily`
  String get doseLine {
    final parts = <String>[
      if ((doseText ?? '').isNotEmpty) doseText!,
      if ((frequencyText ?? '').isNotEmpty) frequencyText!,
      if ((route ?? '').isNotEmpty) route!,
    ];
    return parts.isEmpty ? 'Dose not recorded' : parts.join(' · ');
  }

  /// Large frequency code for the boarding-pass style card (`OD`, `BD`, …).
  String get frequencyCodeLabel => (frequencyCode ?? '—').toUpperCase();

  /// The backend matches `group_key == path` **or** `canonical_name == path`;
  /// the list payload has no `group_key`, so we pass the canonical name.
  String get historyPathSegment => canonicalName;

  bool get isChanged => status == MedicationStatus.previous || historyCount > 1;
}

/// One row of `GET /patients/{id}/medications/{group_key}/history`.
class MedicationHistoryEntry {
  const MedicationHistoryEntry({
    required this.id,
    required this.canonicalName,
    this.rawName,
    this.doseText,
    this.strengthValue,
    this.strengthUnit,
    this.frequencyCode,
    this.frequencyText,
    this.status = MedicationStatus.current,
    this.documentDate,
    this.sourceDocumentFilename,
    this.sourceDocumentId,
    this.createdAt,
  });

  factory MedicationHistoryEntry.fromJson(Map<String, dynamic> json) {
    return MedicationHistoryEntry(
      id: asStringOr(json['id'], ''),
      canonicalName: asStringOr(json['canonical_name'], 'Medication'),
      rawName: asString(json['raw_name']),
      doseText: asString(json['dose_text']),
      strengthValue: asDouble(json['strength_value']),
      strengthUnit: asString(json['strength_unit']),
      frequencyCode: asString(json['frequency_code']),
      frequencyText: asString(json['frequency_text']),
      status: MedicationStatus.fromWire(json['status']),
      documentDate: json['document_date'],
      sourceDocumentFilename: asString(json['source_document_filename']),
      sourceDocumentId: asString(json['source_document_id']),
      createdAt: json['created_at'],
    );
  }

  final String id;
  final String canonicalName;
  final String? rawName;
  final String? doseText;
  final double? strengthValue;
  final String? strengthUnit;
  final String? frequencyCode;
  final String? frequencyText;
  final MedicationStatus status;
  final Object? documentDate;
  final String? sourceDocumentFilename;
  final String? sourceDocumentId;
  final Object? createdAt;

  String get displayName => _titleCase(canonicalName);

  String get doseLine {
    final parts = <String>[
      if ((doseText ?? '').isNotEmpty) doseText!,
      if ((frequencyText ?? '').isNotEmpty) frequencyText!,
    ];
    return parts.isEmpty ? 'Dose not recorded' : parts.join(' · ');
  }

  String get frequencyCodeLabel => (frequencyCode ?? '—').toUpperCase();

  /// Strength line, e.g. `500 mg` or `Strength not recorded`.
  String get strengthLine {
    if (strengthValue == null) return 'Strength not recorded';
    final v = strengthValue!;
    final num =
        v == v.roundToDouble() ? v.toStringAsFixed(0) : v.toStringAsFixed(1);
    final unit = (strengthUnit ?? '').trim();
    return unit.isEmpty ? num : '$num $unit';
  }
}

String _titleCase(String value) {
  if (value.isEmpty) return value;
  return value
      .split(RegExp(r'[\s_\-]+'))
      .where((String p) => p.isNotEmpty)
      .map((String p) => '${p[0].toUpperCase()}${p.substring(1)}')
      .join(' ');
}
