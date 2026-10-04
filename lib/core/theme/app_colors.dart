import 'package:flutter/material.dart';

/// ClinSync colour tokens — plan §7.1.
///
/// Values were colour-picked from `appTheme.jpg`; the sampling log is in
/// `docs/frontend/DESIGN_TOKENS.md`. Screens must never hardcode a colour —
/// they read from this file.
abstract final class AppColors {
  // ── Surfaces ───────────────────────────────────────────────────────────
  /// Outer sage backdrop (the field the phone sits on in the reference).
  static const Color bgBackdrop = Color(0xFFD3DECE);

  /// Main screen canvas — warm off-white. Sampled #F6F6F4.
  static const Color bgCanvas = Color(0xFFF6F6F4);

  /// Cards, buttons, search, nav — pure white.
  static const Color surface = Color(0xFFFFFFFF);

  /// Inner stat strips, banner base, chips, progress tracks.
  static const Color surfaceTint = Color(0xFFF1F5EF);

  /// Slightly deeper sage for banners and pressed fills.
  static const Color surfaceTintDeep = Color(0xFFE6EDE2);

  // ── Accent — exactly one green ──────────────────────────────────────────
  /// Sampled #527A55, the dominant green across reference screens 2 and 3.
  static const Color primary = Color(0xFF527A55);

  /// Pressed state of [primary].
  static const Color primaryDark = Color(0xFF3F6244);

  /// Muted green for the boarding-pass style header band. Sampled #6A866D.
  static const Color primaryMuted = Color(0xFF6A866D);

  /// Soft fills, selected-chip background.
  static const Color primarySoft = Color(0xFFDCE8DA);

  /// Even softer green wash for ambient overlays.
  static const Color primaryWash = Color(0xFFEBF1E8);

  // ── Text ───────────────────────────────────────────────────────────────
  /// Headlines (the black line) and strong body. Sampled #0A0A0A.
  static const Color textPrimary = Color(0xFF141814);

  /// Subtitles, meta, labels.
  static const Color textSecondary = Color(0xFF6E766E);

  /// Inactive nav, placeholders.
  static const Color textTertiary = Color(0xFF9AA29A);

  /// Disabled text.
  static const Color textDisabled = Color(0xFFBFC6BF);

  // ── Lines ──────────────────────────────────────────────────────────────
  /// Hairlines, dashed dividers.
  static const Color divider = Color(0xFFE4E8E2);

  /// Slightly stronger hairline for card edges on tinted surfaces.
  static const Color dividerStrong = Color(0xFFD6DCD4);

  // ── Semantic — clinical safety only (plan §6.6) ────────────────────────
  /// Muted amber; conflicts / review-needed only. Desaturated to fit.
  static const Color warning = Color(0xFFB7791F);
  static const Color warningSoft = Color(0xFFF6EBD8);

  /// Muted red-brown; errors and unverified provenance only.
  static const Color danger = Color(0xFFB3453B);
  static const Color dangerSoft = Color(0xFFF7E6E3);

  /// Confidence bands: high = primary, medium = amber, low = red-brown.
  static const Color confidenceHigh = primary;
  static const Color confidenceMedium = Color(0xFFB7791F);
  static const Color confidenceLow = Color(0xFFA05242);

  static const Color info = Color(0xFF4A7C8C);
  static const Color infoSoft = Color(0xFFE4EFF2);

  /// Text / icons on green fills.
  static const Color onPrimary = Color(0xFFFFFFFF);

  /// Scrim over imagery.
  static const Color scrim = Color(0xFF1B2419);

  /// Confidence micro-bar track.
  static const Color confidenceTrack = Color(0xFFE4E8E2);

  // ── Gradients ──────────────────────────────────────────────────────────

  /// (a) Photo scrim — transparent → rgba(0,0,0,0.65) over the bottom 55%.
  static const LinearGradient photoScrim = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: <Color>[Color(0x00000000), Color(0x00000000), Color(0xA6000000)],
    stops: <double>[0.0, 0.45, 1.0],
  );

  /// (b) Hero fade — transparent → [bgCanvas] at the bottom of the hero.
  static const LinearGradient heroFade = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: <Color>[Color(0x00F6F6F4), Color(0x59F6F6F4), Color(0xFFF6F6F4)],
    stops: <double>[0.0, 0.72, 1.0],
  );

  /// (c) Banner — [surfaceTint] → deeper sage, diagonal.
  static const LinearGradient banner = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: <Color>[Color(0xFFF1F5EF), Color(0xFFE2EADF)],
  );

  /// Ambient video wash — keeps headline contrast at AA over moving imagery.
  static const LinearGradient ambientWash = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: <Color>[Color(0x8CF6F6F4), Color(0x73F6F6F4), Color(0x00F6F6F4)],
    stops: <double>[0.0, 0.55, 1.0],
  );

  /// Monogram fallback tile for patient imagery (no patient photos, §6.5).
  static const LinearGradient monogram = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: <Color>[Color(0xFFE8EFE4), Color(0xFFCFDCC9)],
  );

  /// Verified-memory card left accent.
  static const LinearGradient verifiedAccent = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: <Color>[primary, primaryMuted],
  );
}
