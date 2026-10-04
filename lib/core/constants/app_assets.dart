/// Bundled asset paths — plan §6.5, §7.8.
abstract final class AppAssets {
  const AppAssets._();

  // ── Ambient video (landing-page ambient loops, plan §6.5a, §7.8) ─────────
  //
  // Only the two light loops are shipped. The dark variants are not bundled: the
  // app is light-only (Appendix B), so they would be dead weight, and
  // `darkNoWatermark.mp4` (11.8 MB, 1080p) is over the §7.8 asset budget.
  //
  /// Hero ambient loop shown on Home.
  static const String heroVideo = 'assets/video/hero-light.mp4';

  /// Pre-rendered poster stills, shown instantly and used as the fallback when
  /// the video fails, initialises slowly, or when reduce-motion applies.
  ///
  /// Each poster is a frame of **its own** ambient loop, sage-tinted by
  /// `tools/extract_ambient_stills.py` (plan §6.5a), so poster → video is
  /// invisible.
  static const String heroPoster = 'assets/images/ambient-hero.jpg';

  /// Very subtle ambient loop behind the Brief and Approval headers.
  static const String ribbonVideo = 'assets/video/ribbon-light.mp4';
  static const String ribbonPoster = 'assets/images/ambient-ribbon.jpg';

  // ── Patient-card imagery — never patient photographs (plan §6.5) ────────
  static const String ambientStill = 'assets/images/ambient-mist.jpg';
  static const String ambientStillAlt = 'assets/images/ambient-mist-alt.jpg';
  static const String ambientStillThird =
      'assets/images/ambient-mist-third.jpg';
  static const String ambientHero = 'assets/images/ambient-hero.jpg';

  // ── Offline demo fixtures (plan §14 fallback tier 4) ───────────────────
  static const String demoDir = 'assets/demo/';

  static const String demoPatients = 'assets/demo/patients.json';
  static const String demoOverview = 'assets/demo/overview.json';
  static const String demoDocuments = 'assets/demo/documents.json';
  static const String demoTimeline = 'assets/demo/timeline.json';
  static const String demoMedications = 'assets/demo/medications.json';
  static const String demoMedicationHistory =
      'assets/demo/medication_history.json';
  static const String demoInvestigations = 'assets/demo/investigations.json';
  static const String demoTrend = 'assets/demo/trend_hba1c.json';
  static const String demoIssues = 'assets/demo/issues.json';
  static const String demoFacts = 'assets/demo/facts.json';
  static const String demoEvidence = 'assets/demo/evidence.json';
  static const String demoMemory = 'assets/demo/memory.json';
  static const String demoBrief = 'assets/demo/brief.json';
  static const String demoDocumentStatus = 'assets/demo/document_status.json';
}

/// The 3 ambient stills cycled through the Home patient carousel, in order.
const List<String> kPatientAmbientImages = <String>[
  AppAssets.ambientStill,
  AppAssets.ambientStillAlt,
  AppAssets.ambientStillThird,
];
