import '../constants/enums.dart';
import '../utils/date_format.dart';
import 'json_utils.dart';

/// One row of `GET /patients/{id}/investigations` (latest per test).
class Investigation {
  const Investigation({
    required this.id,
    required this.testName,
    this.testNameRaw,
    this.valueNumeric,
    this.valueText,
    this.unit,
    this.referenceLow,
    this.referenceHigh,
    this.referenceText,
    this.abnormalFlag = AbnormalFlag.unknown,
    this.observedDate,
    this.confidence,
    this.sourceDocumentId,
    this.groupKey = '',
  });

  factory Investigation.fromJson(Map<String, dynamic> json) {
    return Investigation(
      id: asStringOr(json['id'], ''),
      testName: asStringOr(json['test_name'], 'Investigation'),
      testNameRaw: asString(json['test_name_raw']),
      valueNumeric: asDouble(json['value_numeric']),
      valueText: asString(json['value_text']),
      unit: asString(json['unit']),
      referenceLow: asDouble(json['reference_low']),
      referenceHigh: asDouble(json['reference_high']),
      referenceText: asString(json['reference_text']),
      abnormalFlag: AbnormalFlag.fromWire(json['abnormal_flag']),
      observedDate: json['observed_date'],
      confidence: asDouble(json['confidence']),
      sourceDocumentId: asString(json['source_document_id']),
      groupKey:
          asStringOr(json['group_key'], asStringOr(json['test_name'], '')),
    );
  }

  final String id;

  /// Canonical key (`hba1c`, `serum_creatinine`, …).
  final String testName;

  /// Human label as written on the report (`HbA1c`, `Serum Creatinine`).
  final String? testNameRaw;
  final double? valueNumeric;
  final String? valueText;
  final String? unit;
  final double? referenceLow;
  final double? referenceHigh;
  final String? referenceText;
  final AbnormalFlag abnormalFlag;
  final Object? observedDate;
  final double? confidence;
  final String? sourceDocumentId;

  /// Path segment for the trend endpoint. The backend accepts either the
  /// `group_key` or the test name; we prefer `group_key`.
  final String groupKey;

  String get displayName {
    final raw = testNameRaw;
    if (raw != null && raw.isNotEmpty) return raw;
    return _titleCase(testName);
  }

  /// Large value used on `MetricCard`s.
  String get displayValue {
    if (valueText != null && valueText!.isNotEmpty) return valueText!;
    final v = valueNumeric;
    if (v == null) return '—';
    return v == v.roundToDouble() ? v.toStringAsFixed(0) : v.toStringAsFixed(1);
  }

  String get displayUnit => unit ?? '';

  String get referenceLine {
    if ((referenceText ?? '').isNotEmpty) return referenceText!;
    if (referenceLow != null && referenceHigh != null) {
      return '${_trimNum(referenceLow!)} – ${_trimNum(referenceHigh!)}${(unit ?? '').isEmpty ? '' : ' ${unit!}'}';
    }
    if ((unit ?? '').isNotEmpty) return unit!;
    return 'Reference not documented';
  }

  String get observedLabel => AppDate.dayMonth(observedDate);
}

/// One point of `investigation.trend.series`.
class TrendPoint {
  const TrendPoint({
    required this.id,
    required this.value,
    this.unit,
    this.dateLabel,
    this.isoDate,
    this.abnormalFlag = AbnormalFlag.unknown,
  });

  factory TrendPoint.fromJson(Map<String, dynamic> json) {
    final raw = json['value'];
    return TrendPoint(
      id: asStringOr(json['id'], ''),
      // `value` may be a number **or** a string when `value_numeric` is null.
      value: asDouble(raw) ?? double.nan,
      unit: asString(json['unit']),
      dateLabel: asString(json['date']),
      isoDate: json['iso_date'] ?? asString(json['date']),
      abnormalFlag: AbnormalFlag.fromWire(json['abnormal_flag']),
    );
  }

  final String id;
  final double value;
  final String? unit;

  /// `Jan 2026` or `undated`.
  final String? dateLabel;
  final Object? isoDate;
  final AbnormalFlag abnormalFlag;

  bool get hasNumericValue => !value.isNaN;

  String get shortLabel {
    final d = AppDate.tryParse(isoDate);
    if (d == null) {
      return (dateLabel ?? '').isEmpty ? '?' : _short(dateLabel ?? '');
    }
    return _short('${d.day}/${d.month}');
  }

  static String _short(String label) {
    final parts = label.split(RegExp(r'\s+'));
    if (parts.length == 2) {
      return '${parts[0].substring(0, 1)}${parts[1].substring(2)}';
    }
    return label;
  }
}

/// `GET /patients/{id}/investigations/{group_key}/trend`.
///
/// The empty-series variant omits `unit`, `latest_value` and `latest_flag`, so
/// every field is optional.
class InvestigationTrend {
  const InvestigationTrend({
    required this.test,
    this.unit,
    this.series = const <TrendPoint>[],
    this.direction = TrendDirection.stable,
    this.delta = 0,
    this.description,
    this.latestValue,
    this.latestFlag,
  });

  factory InvestigationTrend.fromJson(Map<String, dynamic> json) {
    return InvestigationTrend(
      test: asStringOr(json['test'], 'Investigation'),
      unit: asString(json['unit']),
      series: asMapList(json['series'])
          .map(TrendPoint.fromJson)
          .toList(growable: false),
      direction: TrendDirection.fromWire(json['direction']),
      delta: asDoubleOr(json['delta'], 0),
      description: asString(json['description']),
      latestValue: asDouble(json['latest_value']),
      latestFlag: json['latest_flag'] == null
          ? null
          : AbnormalFlag.fromWire(json['latest_flag']),
    );
  }

  final String test;
  final String? unit;
  final List<TrendPoint> series;
  final TrendDirection direction;
  final double delta;
  final String? description;
  final double? latestValue;
  final AbnormalFlag? latestFlag;

  bool get hasEnoughPoints =>
      series.where((TrendPoint p) => p.hasNumericValue).length >= 2;

  List<TrendPoint> get numericPoints =>
      series.where((TrendPoint p) => p.hasNumericValue).toList(growable: false);

  double? get minValue {
    final pts = numericPoints.map((TrendPoint p) => p.value).toList()..sort();
    return pts.isEmpty ? null : pts.first;
  }

  double? get maxValue {
    final pts = numericPoints.map((TrendPoint p) => p.value).toList()..sort();
    return pts.isEmpty ? null : pts.last;
  }

  String get displayName => _titleCase(test);

  /// Non-causal sentence from the backend, never invented on the client.
  String get descriptionText {
    final d = description;
    if (d != null && d.trim().isNotEmpty) return d.trim();
    return 'No trend description available.';
  }

  String get deltaLabel {
    if (delta == 0) return 'No change';
    final sign = delta > 0 ? '+' : '';
    final v = delta == delta.roundToDouble()
        ? delta.toStringAsFixed(0)
        : delta.toStringAsFixed(1);
    final unit = (this.unit ?? '').trim();
    return '$sign$v${unit.isEmpty ? '' : ' $unit'} · ${direction.label.toLowerCase()}';
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

String _trimNum(double v) =>
    v == v.roundToDouble() ? v.toStringAsFixed(0) : v.toStringAsFixed(1);
