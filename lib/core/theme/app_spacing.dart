/// 4-pt spacing grid — plan §7.3.
abstract final class AppSpacing {
  const AppSpacing._();

  static const double xxs = 4;
  static const double xs = 8;
  static const double sm = 12;
  static const double md = 16;
  static const double lg = 20;
  static const double xl = 24;
  static const double xxl = 32;
  static const double xxxl = 40;

  /// Screen horizontal padding.
  static const double screenH = 20;

  /// Vertical gap between sections.
  static const double sectionGap = 24;

  /// Gap inside cards.
  static const double cardGap = 14;

  /// Carousel item gap.
  static const double carouselGap = 12;

  /// Floating bottom-nav height.
  static const double bottomNavHeight = 72;

  /// Bottom safe padding = nav height + 16.
  static const double bottomSafe = bottomNavHeight + 16;

  /// Sticky action bar height (pill + padding).
  static const double stickyBarHeight = 88;

  /// Reference patient card size (plan §7.6). The reference's names are one
  /// word ("Bali"); clinical names are longer, so the card is wide enough for a
  /// full name plus the trailing arrow button while still bleeding a third card
  /// off the right edge.
  static const double patientCardWidth = 148;
  static const double patientCardHeight = 168;

  /// Page-view fraction that shows ~2.5 cards on a 430 pt screen.
  static const double patientCardViewportFraction = 0.35;

  /// Reference timeline-card thumbnail.
  static const double timelineThumbWidth = 72;
  static const double timelineThumbHeight = 64;

  /// Reference header-block thumbnail.
  static const double headerThumbWidth = 110;
  static const double headerThumbHeight = 84;

  /// Quick-action tile.
  static const double tileSize = 64;
}
