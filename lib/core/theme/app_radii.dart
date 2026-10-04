import 'package:flutter/widgets.dart';

/// Radii — plan §7.4.
abstract final class AppRadii {
  const AppRadii._();

  static const double xs = 8;
  static const double sm = 12;
  static const double md = 16;
  static const double lg = 22;
  static const double xl = 28;

  /// Quick-action tile radius (~18 in the reference).
  static const double tile = 18;

  /// Buttons, search, tabs, status pills.
  static const double pill = 999;

  static const BorderRadius allXs = BorderRadius.all(Radius.circular(xs));
  static const BorderRadius allSm = BorderRadius.all(Radius.circular(sm));
  static const BorderRadius allMd = BorderRadius.all(Radius.circular(md));
  static const BorderRadius allLg = BorderRadius.all(Radius.circular(lg));
  static const BorderRadius allXl = BorderRadius.all(Radius.circular(xl));
  static const BorderRadius allTile = BorderRadius.all(Radius.circular(tile));
  static const BorderRadius allPill = BorderRadius.all(Radius.circular(pill));

  /// Top corners only — used by the boarding-pass header band.
  static const BorderRadius topLg =
      BorderRadius.vertical(top: Radius.circular(lg));
  static const BorderRadius topXl =
      BorderRadius.vertical(top: Radius.circular(xl));
}
