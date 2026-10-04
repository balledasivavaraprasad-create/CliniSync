import '../constants/enums.dart';

/// One entry of `GET /api/v1/specialties`.
///
/// The wire shape is `{id, name, description}`. [Specialty] is the app-side
/// enum: it supplies the Lucide glyph and the offline fallback copy. When the
/// backend grows a specialty the Flutter app does not know about yet, [specialty]
/// resolves to `null` and the entry still renders (neutral glyph + the
/// backend's own name) instead of silently collapsing into General Medicine.
class SpecialtyOption {
  const SpecialtyOption({
    required this.id,
    required this.name,
    this.description,
    this.specialty,
  });

  factory SpecialtyOption.fromJson(Map<String, dynamic> json) {
    final String id = json['id']?.toString().trim() ?? '';
    return SpecialtyOption(
      id: id,
      name: json['name']?.toString().trim().isNotEmpty == true
          ? json['name'].toString().trim()
          : Specialty.fromWire(id).label,
      description: json['description']?.toString(),
      specialty: Specialty.matching(id),
    );
  }

  /// Wire id — what `POST /brief` expects.
  final String id;
  final String name;
  final String? description;

  /// The matching enum value, or `null` for a specialty the app has no glyph for.
  final Specialty? specialty;

  /// Name in `AppIcons.table`; falls back to a neutral stack.
  String get icon => specialty?.icon ?? 'layers';

  /// The bundled mirror, used when the endpoint is unreachable.
  ///
  /// Verified identical to the backend's seed rows apart from `other`, which the
  /// backend labels `Other Specialty` — see `docs/frontend/API_MISMATCHES.md`.
  static List<SpecialtyOption> mirroringBackend() => <SpecialtyOption>[
        for (final Specialty s in Specialty.values)
          SpecialtyOption(id: s.wire, name: s.label, specialty: s),
      ];
}
