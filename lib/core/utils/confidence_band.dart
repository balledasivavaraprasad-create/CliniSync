/// Confidence banding — plan §6.6 rule 2.
///
/// Thresholds come from the backend (`>=0.85 high`, `>=0.60 medium`, else
/// `needs_verification`). The band returned by the API is preferred; it is only
/// computed on the client when the field is absent.
enum ConfidenceBand {
  high('high', 'High', '≥0.85'),
  medium('medium', 'Medium', '0.60–0.84'),
  needsVerification('needs_verification', 'Needs verification', '<0.60');

  const ConfidenceBand(this.wire, this.label, this.threshold);

  /// Backend enum string.
  final String wire;

  /// Doctor-facing label.
  final String label;

  /// Human-readable threshold, shown in the badge tooltip.
  final String threshold;

  static ConfidenceBand fromWire(Object? raw, {double? confidence}) {
    final String s = raw?.toString().trim().toLowerCase() ?? '';
    for (final ConfidenceBand b in ConfidenceBand.values) {
      if (b.wire == s) return b;
    }
    return fromValue(confidence);
  }

  /// Compute from a numeric confidence when the band is absent.
  static ConfidenceBand fromValue(double? v) {
    if (v == null) return ConfidenceBand.needsVerification;
    if (v >= 0.85) return ConfidenceBand.high;
    if (v >= 0.60) return ConfidenceBand.medium;
    return ConfidenceBand.needsVerification;
  }

  /// Filled segments in the 3-segment micro-bar.
  int get filledSegments => switch (this) {
        ConfidenceBand.high => 3,
        ConfidenceBand.medium => 2,
        ConfidenceBand.needsVerification => 1,
      };
}

/// `verification_status` emitted by the backend.
enum VerificationStatus {
  unverified('unverified', 'AI-generated · Unverified'),
  needsVerification('needs_verification', 'Needs verification'),
  doctorVerified('doctor_verified', 'Doctor approved'),
  doctorRejected('doctor_rejected', 'Rejected by doctor');

  const VerificationStatus(this.wire, this.label);

  final String wire;
  final String label;

  static VerificationStatus fromWire(Object? raw) {
    final String s = raw?.toString().trim().toLowerCase() ?? '';
    for (final VerificationStatus v in VerificationStatus.values) {
      if (v.wire == s) return v;
    }
    return VerificationStatus.unverified;
  }
}
