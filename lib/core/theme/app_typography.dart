import 'package:flutter/material.dart';

import 'app_colors.dart';

/// Font families bundled as local assets — plan §7.2.
///
/// The serif is the landing page's own serif (Cormorant Garamond, loaded by
/// `index.html`), which is visually compatible with the reference headline, so
/// plan §0.2 rule 10 is satisfied and no runtime font download is needed.
abstract final class AppFont {
  const AppFont._();

  /// Editorial serif — headlines, screen titles, large numbers.
  static const String serif = 'CormorantGaramond';

  /// Humanist sans — UI, body, labels.
  static const String sans = 'Inter';

  /// Mono — verbatim source spans.
  static const String mono = 'JetBrainsMono';
}

/// Typography scale — plan §7.2. Style names are fixed by the plan.
abstract final class AppTypography {
  const AppTypography._();

  static TextStyle _serif({
    required double size,
    double height = 1.15,
    FontWeight weight = FontWeight.w400,
    double letterSpacing = 0,
    Color color = AppColors.textPrimary,
  }) {
    return TextStyle(
      fontFamily: AppFont.serif,
      fontSize: size,
      height: height,
      fontWeight: weight,
      letterSpacing: letterSpacing,
      color: color,
      leadingDistribution: TextLeadingDistribution.even,
      // Cormorant Garamond ships oldstyle figures by default, where `0` is
      // x-height and reads as a lowercase `o` — "60-Second" rendered as
      // "6o-Second", and a dose could be misread. Lining + tabular figures keep
      // every digit full-height in clinical text.
      fontFeatures: const <FontFeature>[
        FontFeature.liningFigures(),
        FontFeature.tabularFigures(),
      ],
    );
  }

  static TextStyle _sans({
    required double size,
    double height = 1.4,
    FontWeight weight = FontWeight.w400,
    double letterSpacing = 0,
    Color color = AppColors.textPrimary,
  }) {
    return TextStyle(
      fontFamily: AppFont.sans,
      fontSize: size,
      height: height,
      fontWeight: weight,
      letterSpacing: letterSpacing,
      color: color,
    );
  }

  /// Home hero — 3 lines; line 1 `textPrimary`, lines 2–3 [primary].
  static TextStyle get displayHero => _serif(
        size: 40,
        height: 1.08,
        weight: FontWeight.w500,
        letterSpacing: -0.4,
      );

  static TextStyle get displayHeroAccent =>
      displayHero.copyWith(color: AppColors.primary);

  /// Top-bar titles.
  static TextStyle get titleScreen =>
      _serif(size: 20, height: 1.2, weight: FontWeight.w500);

  /// Grey sub-line under a top-bar title.
  static TextStyle get titleScreenSub => _sans(
        size: 12,
        height: 1.3,
        color: AppColors.textSecondary,
      );

  /// Patient name in the header block.
  static TextStyle get titleHeader =>
      _serif(size: 22, height: 1.15, weight: FontWeight.w500);

  /// Serif title for full-screen sub-pages (Specialty, Voice prompt).
  static TextStyle get titlePage =>
      _serif(size: 28, height: 1.12, weight: FontWeight.w500);

  /// Section headers (`Recent Patients`).
  static TextStyle get titleSection => _sans(
        size: 17,
        height: 1.25,
        weight: FontWeight.w600,
        letterSpacing: -0.1,
      );

  /// Card titles.
  static TextStyle get titleCard => _sans(
        size: 16,
        height: 1.3,
        weight: FontWeight.w600,
        letterSpacing: -0.1,
      );

  static TextStyle get body => _sans(size: 14, height: 1.45);

  static TextStyle get bodyStrong =>
      _sans(size: 14, height: 1.45, weight: FontWeight.w600);

  /// Dot-separated bullet lines on timeline cards.
  static TextStyle get bodyBullet =>
      _sans(size: 12.5, height: 1.5, color: AppColors.textSecondary);

  /// Labels (`Flight` / `Gate` / `Seat` style).
  static TextStyle get label => _sans(
      size: 12,
      height: 1.3,
      weight: FontWeight.w500,
      color: AppColors.textSecondary);

  /// Meta, tab labels in nav.
  static TextStyle get caption =>
      _sans(size: 11, height: 1.3, color: AppColors.textSecondary);

  /// `BOARDING PASS`-style headers.
  static TextStyle get capsLabel =>
      _sans(size: 11, height: 1.2, weight: FontWeight.w600, letterSpacing: 0.8);

  /// `CGK`/`DPS`-style codes.
  static TextStyle get numberLarge => _serif(
        size: 30,
        height: 1.05,
        weight: FontWeight.w600,
        letterSpacing: -0.2,
      );

  /// `26°`-style values where a grotesque reads better.
  static TextStyle get numberLargeSans => _sans(
        size: 30,
        height: 1.05,
        weight: FontWeight.w700,
        letterSpacing: -0.6,
      );

  /// Stat values.
  static TextStyle get numberStat => _sans(
      size: 15, height: 1.2, weight: FontWeight.w600, letterSpacing: -0.1);

  /// CTA text.
  static TextStyle get button => _sans(
        size: 16,
        height: 1.2,
        weight: FontWeight.w600,
        letterSpacing: -0.1,
        color: AppColors.onPrimary,
      );

  /// `See all`.
  static TextStyle get link => _sans(
      size: 14, height: 1.2, weight: FontWeight.w500, color: AppColors.primary);

  /// Verbatim source text inside evidence quotes.
  static TextStyle get verbatim => const TextStyle(
        fontFamily: AppFont.mono,
        fontSize: 12,
        height: 1.55,
        color: AppColors.textPrimary,
      );

  /// Quick-action tile label.
  static TextStyle get tileLabel => _sans(
        size: 12,
        height: 1.25,
        weight: FontWeight.w500,
        color: AppColors.textSecondary,
        letterSpacing: -0.1,
      );

  /// Pill-tab label.
  static TextStyle get tabLabel =>
      _sans(size: 14, height: 1.2, weight: FontWeight.w500);

  /// Bottom-nav label.
  static TextStyle get navLabel =>
      _sans(size: 11, height: 1.2, weight: FontWeight.w500);
}

/// Maps the scale onto [TextTheme] so Material widgets inherit it.
abstract final class AppTextTheme {
  const AppTextTheme._();

  /// Lining + tabular figures for the serif, matching [AppTypography._serif].
  static const List<FontFeature> _serifFigures = <FontFeature>[
    FontFeature.liningFigures(),
    FontFeature.tabularFigures(),
  ];

  static TextTheme build() {
    return const TextTheme(
      displayLarge: TextStyle(
        fontFamily: AppFont.serif,
        fontSize: 40,
        height: 1.08,
        fontWeight: FontWeight.w500,
        fontFeatures: _serifFigures,
      ),
      displayMedium: TextStyle(
        fontFamily: AppFont.serif,
        fontSize: 28,
        height: 1.12,
        fontWeight: FontWeight.w500,
        fontFeatures: _serifFigures,
      ),
      headlineMedium: TextStyle(
        fontFamily: AppFont.serif,
        fontSize: 22,
        height: 1.15,
        fontWeight: FontWeight.w500,
        fontFeatures: _serifFigures,
      ),
      headlineSmall: TextStyle(
        fontFamily: AppFont.sans,
        fontSize: 17,
        height: 1.25,
        fontWeight: FontWeight.w600,
      ),
      titleLarge: TextStyle(
        fontFamily: AppFont.sans,
        fontSize: 16,
        height: 1.3,
        fontWeight: FontWeight.w600,
      ),
      titleMedium: TextStyle(
        fontFamily: AppFont.sans,
        fontSize: 14,
        height: 1.45,
        fontWeight: FontWeight.w600,
      ),
      bodyLarge:
          TextStyle(fontFamily: AppFont.sans, fontSize: 14, height: 1.45),
      bodyMedium:
          TextStyle(fontFamily: AppFont.sans, fontSize: 12.5, height: 1.5),
      bodySmall: TextStyle(fontFamily: AppFont.sans, fontSize: 11, height: 1.3),
      labelLarge: TextStyle(
          fontFamily: AppFont.sans,
          fontSize: 16,
          height: 1.2,
          fontWeight: FontWeight.w600),
      labelMedium: TextStyle(
        fontFamily: AppFont.sans,
        fontSize: 12,
        height: 1.3,
        fontWeight: FontWeight.w500,
      ),
      labelSmall: TextStyle(
        fontFamily: AppFont.sans,
        fontSize: 11,
        height: 1.2,
        fontWeight: FontWeight.w600,
        letterSpacing: 0.8,
      ),
    );
  }
}
