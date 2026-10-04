/// Tolerant JSON readers — plan §8 "Models: tolerant parsing".
///
/// Unknown fields are ignored, missing optional fields become null, and every
/// reader coerces loosely so a schema tweak never crashes a screen.
library;

int? asInt(Object? v) {
  if (v == null) return null;
  if (v is int) return v;
  if (v is double) return v.toInt();
  if (v is num) return v.toInt();
  return int.tryParse(v.toString().trim());
}

int asIntOr(Object? v, int fallback) => asInt(v) ?? fallback;

double? asDouble(Object? v) {
  if (v == null) return null;
  if (v is double) return v;
  if (v is num) return v.toDouble();
  return double.tryParse(v.toString().trim().replaceAll(',', ''));
}

double asDoubleOr(Object? v, double fallback) => asDouble(v) ?? fallback;

String? asString(Object? v) {
  if (v == null) return null;
  final s = v.toString().trim();
  return s.isEmpty ? null : s;
}

String asStringOr(Object? v, String fallback) => asString(v) ?? fallback;

bool asBool(Object? v, {bool fallback = false}) {
  if (v == null) return fallback;
  if (v is bool) return v;
  final s = v.toString().toLowerCase();
  if (s == 'true' || s == '1' || s == 'yes') return true;
  if (s == 'false' || s == '0' || s == 'no') return false;
  return fallback;
}

Map<String, dynamic> asMap(Object? v) {
  if (v is Map) return Map<String, dynamic>.from(v);
  return const <String, dynamic>{};
}

List<dynamic> asList(Object? v) {
  if (v is List) return v;
  return const <dynamic>[];
}

List<Map<String, dynamic>> asMapList(Object? v) {
  return asList(v)
      .whereType<Map>()
      .map(Map<String, dynamic>.from)
      .toList(growable: false);
}

List<String> asStringList(Object? v) {
  return asList(v)
      .map((e) => e.toString())
      .where((e) => e.isNotEmpty)
      .toList(growable: false);
}

DateTime? asDate(Object? v) {
  if (v == null) return null;
  if (v is DateTime) return v;
  return DateTime.tryParse(v.toString());
}
