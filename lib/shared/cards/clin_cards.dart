import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/animations/motion.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_radii.dart';
import '../../core/theme/app_shadows.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/utils/confidence_band.dart';
import '../../core/utils/date_format.dart';
import '../loading/states.dart';
import '../widgets/app_icons.dart';
import '../widgets/primitives.dart';

IconData icon(String name) => AppIcons.byName(name);

// ═══════════════════════════════════════════════════════════════════════════
// HOME — reference screen 1
// ═══════════════════════════════════════════════════════════════════════════

/// From the reference destination card — plan §7.6.
///
/// 118 × 156, radius 22, ambient image or gradient + serif monogram, photo
/// scrim, bottom-left white name + subtitle, bottom-right 32 px white circular
/// arrow button. Never a patient photograph (plan §6.5).
class PatientCard extends StatelessWidget {
  const PatientCard({
    super.key,
    required this.name,
    required this.subtitle,
    this.monogram = '',
    this.imageAsset,
    this.onTap,
    this.width = AppSpacing.patientCardWidth,
    this.height = AppSpacing.patientCardHeight,
    this.badgeLabel,
  });

  final String name;
  final String subtitle;
  final String monogram;
  final String? imageAsset;
  final VoidCallback? onTap;
  final double width;
  final double height;
  final String? badgeLabel;

  @override
  Widget build(BuildContext context) {
    return PressScale(
      onTap: onTap,
      child: Container(
        width: width,
        height: height,
        decoration: BoxDecoration(
          color: AppColors.surfaceTintDeep,
          borderRadius: AppRadii.allLg,
          boxShadow: AppShadows.card,
          image: imageAsset == null
              ? null
              : DecorationImage(
                  image: AssetImage(imageAsset!), fit: BoxFit.cover),
        ),
        clipBehavior: Clip.antiAlias,
        child: Stack(
          fit: StackFit.expand,
          children: <Widget>[
            if (imageAsset == null)
              DecoratedBox(
                decoration: const BoxDecoration(gradient: AppColors.monogram),
                child: Center(
                  child: Text(
                    monogram,
                    style: AppTypography.titlePage.copyWith(
                      fontSize: 30,
                      color: AppColors.primaryDark.withValues(alpha: 0.55),
                    ),
                  ),
                ),
              ),
            const DecoratedBox(
                decoration: BoxDecoration(gradient: AppColors.photoScrim)),
            Positioned(
              left: AppSpacing.sm,
              right: AppSpacing.sm,
              bottom: AppSpacing.sm,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  // The reference names are one word ("Bali"); clinical names are
                  // longer, so the name gets the full card width and the subtitle
                  // shares the bottom row with the arrow.
                  Text(
                    name,
                    style: AppTypography.titleCard.copyWith(
                      color: AppColors.onPrimary,
                      fontSize: 15,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 1),
                  Row(
                    children: <Widget>[
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisSize: MainAxisSize.min,
                          children: <Widget>[
                            Text(
                              subtitle,
                              style: AppTypography.caption.copyWith(
                                color:
                                    AppColors.onPrimary.withValues(alpha: 0.82),
                                fontSize: 10.5,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                            if (badgeLabel != null)
                              Padding(
                                padding: const EdgeInsets.only(top: 5),
                                child: Container(
                                  padding: const EdgeInsets.symmetric(
                                      horizontal: 6, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: AppColors.onPrimary
                                        .withValues(alpha: 0.22),
                                    borderRadius: AppRadii.allPill,
                                  ),
                                  child: Text(
                                    badgeLabel!,
                                    style: AppTypography.capsLabel.copyWith(
                                      color: AppColors.onPrimary,
                                      fontSize: 8.5,
                                      letterSpacing: 0.3,
                                    ),
                                  ),
                                ),
                              ),
                          ],
                        ),
                      ),
                      const SizedBox(width: AppSpacing.xs),
                      Container(
                        width: 28,
                        height: 28,
                        decoration: const BoxDecoration(
                          color: AppColors.surface,
                          shape: BoxShape.circle,
                          boxShadow: AppShadows.tile,
                        ),
                        alignment: Alignment.center,
                        child: const Icon(
                          LucideIcons.arrowRight,
                          size: 14,
                          color: AppColors.textPrimary,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 64 × 64 white rounded-square, 26 px thin-line icon, label centred under.
class QuickActionTile extends StatelessWidget {
  const QuickActionTile({
    super.key,
    required this.iconName,
    required this.label,
    this.onTap,
    this.size = AppSpacing.tileSize,
    this.selected = false,
  });

  final String iconName;
  final String label;
  final VoidCallback? onTap;
  final double size;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    return PressScale(
      onTap: onTap,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Container(
            width: size,
            height: size,
            decoration: BoxDecoration(
              color: selected ? AppColors.primarySoft : AppColors.surface,
              borderRadius: AppRadii.allTile,
              boxShadow: AppShadows.tile,
              border: selected
                  ? Border.all(color: AppColors.primary, width: 1.6)
                  : null,
            ),
            alignment: Alignment.center,
            child: Icon(
              icon(iconName),
              size: 26,
              color: selected ? AppColors.primaryDark : AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            label,
            style: AppTypography.tileLabel.copyWith(fontSize: 11.5),
            textAlign: TextAlign.center,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}

/// Gradient `surfaceTint` card, sparkle left, two-line text, right logo mark.
class AIBanner extends StatelessWidget {
  const AIBanner({
    super.key,
    required this.title,
    required this.subtitle,
    this.onTap,
    this.iconName = 'sparkles',
  });

  final String title;
  final String subtitle;
  final VoidCallback? onTap;
  final String iconName;

  @override
  Widget build(BuildContext context) {
    return PressScale(
      onTap: onTap,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(AppSpacing.md),
        decoration: const BoxDecoration(
          gradient: AppColors.banner,
          borderRadius: AppRadii.allLg,
          boxShadow: AppShadows.card,
        ),
        child: Row(
          children: <Widget>[
            Icon(icon(iconName), size: 24, color: AppColors.primary),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  Text(title, style: AppTypography.bodyStrong),
                  const SizedBox(height: 2),
                  Text(
                    subtitle,
                    style: AppTypography.bodyBullet.copyWith(fontSize: 11.5),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            const SizedBox(width: AppSpacing.xs),
            // Plan §6.5: a plain logo mark in a soft circle — never an invented
            // mascot character.
            Container(
              width: 44,
              height: 44,
              decoration: const BoxDecoration(
                  color: AppColors.surface, shape: BoxShape.circle),
              alignment: Alignment.center,
              child: Container(
                width: 30,
                height: 30,
                decoration: const BoxDecoration(
                  color: AppColors.primarySoft,
                  shape: BoxShape.circle,
                ),
                alignment: Alignment.center,
                child: Text(
                  'C',
                  style: AppTypography.titleScreen.copyWith(
                    color: AppColors.primaryDark,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// OVERVIEW — reference screen 2
// ═══════════════════════════════════════════════════════════════════════════

/// Title + optional edit pencil, meta line, `AvatarStack`, trailing thumbnail.
class HeaderBlock extends StatelessWidget {
  const HeaderBlock({
    super.key,
    required this.name,
    required this.metaLine,
    this.documentTypeIcons = const <String>[],
    this.documentOverflow = 0,
    this.onOverflowTap,
    this.thumbnailAsset,
    this.thumbnailIcon = 'fileText',
    this.onEdit,
    this.chips = const <Widget>[],
  });

  final String name;
  final String metaLine;
  final List<String> documentTypeIcons;
  final int documentOverflow;
  final VoidCallback? onOverflowTap;
  final String? thumbnailAsset;
  final String thumbnailIcon;
  final VoidCallback? onEdit;
  final List<Widget> chips;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Row(
                  children: <Widget>[
                    Flexible(
                      child: Text(
                        name,
                        style: AppTypography.titleHeader,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    if (onEdit != null) ...<Widget>[
                      const SizedBox(width: AppSpacing.xs),
                      GestureDetector(
                        onTap: onEdit,
                        child: Icon(AppIcons.byName('pencil'),
                            size: 15, color: AppColors.textSecondary),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 2),
                Text(
                  metaLine,
                  style: AppTypography.bodyBullet,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                if (chips.isNotEmpty) ...<Widget>[
                  const SizedBox(height: AppSpacing.xs),
                  Wrap(spacing: 6, runSpacing: 6, children: chips),
                ],
                const SizedBox(height: AppSpacing.sm),
                AvatarStack(
                  items: documentTypeIcons,
                  overflowExtra: documentOverflow,
                  onOverflowTap: onOverflowTap,
                ),
              ],
            ),
          ),
          const SizedBox(width: AppSpacing.sm),
          ClipRRect(
            borderRadius: AppRadii.allMd,
            child: SizedBox(
              width: AppSpacing.headerThumbWidth,
              height: AppSpacing.headerThumbHeight,
              child: thumbnailAsset != null
                  ? Image.asset(thumbnailAsset!, fit: BoxFit.cover)
                  : Container(
                      decoration:
                          const BoxDecoration(gradient: AppColors.monogram),
                      alignment: Alignment.center,
                      child: Icon(icon(thumbnailIcon),
                          size: 30, color: AppColors.primaryDark),
                    ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Outline icon + `label` over `numberStat`.
class StatItem extends StatelessWidget {
  const StatItem({
    super.key,
    required this.iconName,
    required this.label,
    required this.value,
    this.onTap,
  });

  final String iconName;
  final String label;
  final String value;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return PressScale(
      onTap: onTap,
      scale: 0.96,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Icon(icon(iconName), size: 18, color: AppColors.textPrimary),
          const SizedBox(width: AppSpacing.xs),
          Flexible(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Text(
                  label,
                  style: AppTypography.label
                      .copyWith(fontSize: 11, color: AppColors.textSecondary),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                Text(
                  value,
                  style: AppTypography.numberStat,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// White r 22 `shadowCard`; check-circle + green title + meta lines + trailing
/// mini illustration + chevron; bottom inner `surfaceTint` strip of stat items.
class InsightCard extends StatelessWidget {
  const InsightCard({
    super.key,
    required this.title,
    this.metaLine1,
    this.metaLine2,
    this.stats = const <Widget>[],
    this.onTap,
    this.trailingIconName = 'mapPin',
    this.statusPill,
    this.checkIcon = 'check',
    this.titleColor,
  });

  final String title;
  final String? metaLine1;
  final String? metaLine2;
  final List<Widget> stats;
  final VoidCallback? onTap;

  /// The mini route illustration standing in for the reference's map doodle.
  final String trailingIconName;
  final Widget? statusPill;
  final String checkIcon;
  final Color? titleColor;

  @override
  Widget build(BuildContext context) {
    return SurfaceCard(
      onTap: onTap,
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Container(
                width: 26,
                height: 26,
                decoration: const BoxDecoration(
                    color: AppColors.primary, shape: BoxShape.circle),
                alignment: Alignment.center,
                child:
                    Icon(icon(checkIcon), size: 14, color: AppColors.onPrimary),
              ),
              const SizedBox(width: AppSpacing.xs),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    Text(
                      title,
                      style: AppTypography.titleCard.copyWith(
                        color: titleColor ?? AppColors.primary,
                        fontSize: 15.5,
                      ),
                    ),
                    if (statusPill != null) ...<Widget>[
                      const SizedBox(height: 5),
                      statusPill!,
                    ],
                  ],
                ),
              ),
              const SizedBox(width: AppSpacing.xs),
              _MiniRouteIllustration(iconName: trailingIconName),
              const SizedBox(width: AppSpacing.xs),
              Icon(AppIcons.byName('chevronRight'),
                  size: 18, color: AppColors.textTertiary),
            ],
          ),
          if (metaLine1 != null || metaLine2 != null) ...<Widget>[
            const SizedBox(height: AppSpacing.xs),
            Padding(
              padding: const EdgeInsets.only(left: 34),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  if (metaLine1 != null)
                    Text(
                      metaLine1!,
                      style: AppTypography.bodyBullet.copyWith(fontSize: 11.5),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  if (metaLine2 != null)
                    Text(
                      metaLine2!,
                      style: AppTypography.bodyBullet.copyWith(fontSize: 11.5),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                ],
              ),
            ),
          ],
          if (stats.isNotEmpty) ...<Widget>[
            const SizedBox(height: AppSpacing.sm),
            Container(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.sm,
                vertical: AppSpacing.sm,
              ),
              decoration: const BoxDecoration(
                  color: AppColors.surfaceTint, borderRadius: AppRadii.allMd),
              child: IntrinsicHeight(
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: <Widget>[
                    for (int i = 0; i < stats.length; i++) ...<Widget>[
                      Expanded(child: stats[i]),
                      if (i < stats.length - 1)
                        Container(
                            width: 1,
                            color: AppColors.divider,
                            margin: const EdgeInsets.symmetric(horizontal: 6)),
                    ],
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// The reference's dashed route doodle: two green pins joined by a dashed line.
class _MiniRouteIllustration extends StatelessWidget {
  const _MiniRouteIllustration({required this.iconName});

  final String iconName;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 74,
      height: 44,
      child: Stack(
        children: <Widget>[
          Positioned.fill(
            child: CustomPaint(painter: _DashedRoutePainter()),
          ),
          Positioned(
            left: 2,
            top: 4,
            child: Icon(icon('mapPin'), size: 17, color: AppColors.primary),
          ),
          Positioned(
            right: 2,
            bottom: 4,
            child: Icon(icon('mapPin'), size: 17, color: AppColors.primary),
          ),
          Positioned(
            right: 8,
            top: 2,
            child: Icon(icon(iconName), size: 12, color: AppColors.primarySoft),
          ),
        ],
      ),
    );
  }
}

class _DashedRoutePainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final Paint paint = Paint()
      ..color = AppColors.primary
      ..strokeWidth = 1.6
      ..style = PaintingStyle.stroke;

    final Path path = Path()
      ..moveTo(12, 12)
      ..cubicTo(size.width * 0.35, size.height * 0.95, size.width * 0.6,
          size.height * 0.1, size.width - 12, size.height - 12);

    // Dashed effect.
    for (final uiMetrics in path.computeMetrics()) {
      double distance = 0;
      while (distance < uiMetrics.length) {
        canvas.drawPath(
          uiMetrics.extractPath(
              distance, math.min(distance + 4, uiMetrics.length)),
          paint,
        );
        distance += 7;
      }
    }
  }

  @override
  bool shouldRepaint(_DashedRoutePainter oldDelegate) => false;
}

/// Left column: tiny label, 32 px `primary` circle, 2 px dotted connector.
class TimelineRail extends StatelessWidget {
  const TimelineRail({
    super.key,
    required this.label,
    required this.number,
    this.isFirst = false,
    this.isLast = false,
    this.pulsing = false,
  });

  final String label;
  final String number;
  final bool isFirst;
  final bool isLast;
  final bool pulsing;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 44,
      child: Column(
        children: <Widget>[
          SizedBox(
            height: 14,
            child: Text(
              label,
              style: AppTypography.label
                  .copyWith(fontSize: 10, color: AppColors.textSecondary),
            ),
          ),
          const SizedBox(height: 3),
          SoftPulse(
            active: pulsing,
            child: Container(
              width: 32,
              height: 32,
              decoration: const BoxDecoration(
                  color: AppColors.primary, shape: BoxShape.circle),
              alignment: Alignment.center,
              child: Text(
                number,
                style: AppTypography.bodyStrong.copyWith(
                  color: AppColors.onPrimary,
                  fontSize: 14,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ),
          if (!isLast)
            Expanded(
              child: CustomPaint(
                size: const Size(2, 20),
                painter: _DotConnectorPainter(),
              ),
            ),
        ],
      ),
    );
  }
}

class _DotConnectorPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final Paint paint = Paint()
      ..color = AppColors.primarySoft
      ..strokeWidth = 2
      ..strokeCap = StrokeCap.round;
    const double dash = 2.0;
    const double gap = 4.0;
    double y = 0;
    while (y < size.height) {
      canvas.drawLine(
        Offset(size.width / 2, y),
        Offset(size.width / 2, (y + dash).clamp(0, size.height)),
        paint,
      );
      y += dash + gap;
    }
  }

  @override
  bool shouldRepaint(_DotConnectorPainter oldDelegate) => false;
}

/// White r 20 card; leading green line icon, title, trailing chevron button,
/// two `bodyBullet` lines, trailing 72 × 64 thumbnail.
class TimelineCard extends StatelessWidget {
  const TimelineCard({
    super.key,
    required this.iconName,
    required this.title,
    this.bullet1,
    this.bullet2,
    this.onTap,
    this.onChevronTap,
    this.thumbnailAsset,
    this.thumbnailIcon,
    this.trailing,
  });

  final String iconName;
  final String title;
  final String? bullet1;
  final String? bullet2;
  final VoidCallback? onTap;
  final VoidCallback? onChevronTap;
  final String? thumbnailAsset;
  final String? thumbnailIcon;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return SurfaceCard(
      onTap: onTap,
      radius: 20,
      padding: const EdgeInsets.all(AppSpacing.sm),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Icon(icon(iconName), size: 18, color: AppColors.primary),
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Row(
                  children: <Widget>[
                    Expanded(
                      child: Text(
                        title,
                        style: AppTypography.titleCard.copyWith(fontSize: 14.5),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    if (onChevronTap != null)
                      CircleIconButton(
                        icon: 'chevronRight',
                        size: 26,
                        iconSize: 14,
                        onTap: onChevronTap,
                        background: AppColors.surfaceTint,
                      ),
                  ],
                ),
                if (bullet1 != null) ...<Widget>[
                  const SizedBox(height: 5),
                  _BulletLine(text: bullet1!),
                ],
                if (bullet2 != null) _BulletLine(text: bullet2!),
                if (trailing != null) ...<Widget>[
                  const SizedBox(height: AppSpacing.xs),
                  trailing!,
                ],
              ],
            ),
          ),
          if (thumbnailAsset != null || thumbnailIcon != null) ...<Widget>[
            const SizedBox(width: AppSpacing.xs),
            ClipRRect(
              borderRadius: AppRadii.allSm,
              child: SizedBox(
                width: AppSpacing.timelineThumbWidth,
                height: AppSpacing.timelineThumbHeight,
                child: thumbnailAsset != null
                    ? Image.asset(thumbnailAsset!, fit: BoxFit.cover)
                    : Container(
                        decoration:
                            const BoxDecoration(gradient: AppColors.monogram),
                        alignment: Alignment.center,
                        child: Icon(
                          icon(thumbnailIcon ?? 'fileText'),
                          size: 22,
                          color: AppColors.primaryDark,
                        ),
                      ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _BulletLine extends StatelessWidget {
  const _BulletLine({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 2),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Padding(
            padding: const EdgeInsets.only(top: 5, right: 6, left: 1),
            child: Container(
              width: 3.5,
              height: 3.5,
              decoration: const BoxDecoration(
                  color: AppColors.textTertiary, shape: BoxShape.circle),
            ),
          ),
          Expanded(
            child: Text(
              text,
              style: AppTypography.bodyBullet,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }
}

/// White r 20 row; 64 × 64 rounded thumbnail, `label` + bold title + meta,
/// trailing chevron.
class LinkRowCard extends StatelessWidget {
  const LinkRowCard({
    super.key,
    required this.title,
    this.label,
    this.meta,
    this.onTap,
    this.thumbnailAsset,
    this.thumbnailIcon = 'fileText',
    this.leading,
    this.trailing,
    this.thumbnailSize = 64,
    this.radius = 20,
  });

  final String title;
  final String? label;
  final String? meta;
  final VoidCallback? onTap;
  final String? thumbnailAsset;
  final String thumbnailIcon;
  final Widget? leading;
  final Widget? trailing;
  final double thumbnailSize;
  final double radius;

  @override
  Widget build(BuildContext context) {
    return SurfaceCard(
      onTap: onTap,
      radius: radius,
      padding: const EdgeInsets.all(AppSpacing.sm),
      child: Row(
        children: <Widget>[
          if (thumbnailAsset != null) ...<Widget>[
            ClipRRect(
              borderRadius: AppRadii.allMd,
              child: SizedBox(
                width: thumbnailSize,
                height: thumbnailSize,
                child: thumbnailAsset != null
                    ? Image.asset(thumbnailAsset!, fit: BoxFit.cover)
                    : Container(
                        decoration:
                            const BoxDecoration(gradient: AppColors.monogram),
                        alignment: Alignment.center,
                        child: Icon(icon(thumbnailIcon),
                            size: 22, color: AppColors.primaryDark),
                      ),
              ),
            ),
            const SizedBox(width: AppSpacing.sm),
          ],
          if (leading != null) ...<Widget>[
            leading!,
            const SizedBox(width: AppSpacing.sm)
          ],
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                if (label != null)
                  Text(label!,
                      style: AppTypography.label.copyWith(fontSize: 11)),
                Text(
                  title,
                  style: AppTypography.titleCard.copyWith(fontSize: 14.5),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                if (meta != null)
                  Text(
                    meta!,
                    style: AppTypography.bodyBullet.copyWith(fontSize: 11.5),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
              ],
            ),
          ),
          if (trailing != null) ...<Widget>[
            const SizedBox(width: AppSpacing.xs),
            trailing!,
          ] else if (onTap != null) ...<Widget>[
            const SizedBox(width: AppSpacing.xs),
            Icon(AppIcons.byName('chevronRight'),
                size: 18, color: AppColors.textTertiary),
          ],
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// DETAIL — reference screen 3
// ═══════════════════════════════════════════════════════════════════════════

/// Boarding-pass card — plan §7.6.
///
/// Muted-green header band with `capsLabel` + status pill + icon, a concave
/// transition into the white body (custom clipper), a 3-column route layout,
/// dotted connector with centred icon + caption, dashed divider, a 3-column
/// key/value row and a trailing evidence tile. **Never a fake QR code.**
class TicketCard extends StatelessWidget {
  const TicketCard({
    super.key,
    required this.headerLabel,
    required this.statusLabel,
    this.headerIconName = 'plane',
    this.leftBlock,
    this.rightBlock,
    this.connectorCaption,
    this.connectorIconName = 'replace',
    this.keyValues = const <Widget>[],
    this.trailingTile,
    this.onTap,
    this.notches = true,
  });

  /// Small-caps header, e.g. `MEDICATION CHANGE`.
  final String headerLabel;
  final String statusLabel;
  final String headerIconName;

  /// A 3-column block: `{label, code, time, date}` style.
  final Widget? leftBlock;
  final Widget? rightBlock;
  final String? connectorCaption;
  final String connectorIconName;
  final List<Widget> keyValues;
  final Widget? trailingTile;
  final VoidCallback? onTap;
  final bool notches;

  @override
  Widget build(BuildContext context) {
    return PressScale(
      onTap: onTap,
      child: ClipPath(
        clipper: _TicketClipper(),
        child: Container(
          decoration: const BoxDecoration(
            color: AppColors.surface,
            borderRadius: AppRadii.allLg,
            boxShadow: AppShadows.card,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              // ── Header band
              Container(
                padding: const EdgeInsets.fromLTRB(
                    AppSpacing.md, AppSpacing.sm, AppSpacing.md, AppSpacing.xl),
                decoration: const BoxDecoration(
                  color: AppColors.primaryMuted,
                  borderRadius: AppRadii.topLg,
                ),
                child: Row(
                  children: <Widget>[
                    Expanded(
                      child: Text(
                        headerLabel,
                        style: AppTypography.capsLabel
                            .copyWith(color: AppColors.onPrimary),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    const SizedBox(width: AppSpacing.xs),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 10, vertical: 5),
                      decoration: BoxDecoration(
                        border: Border.all(
                          color: AppColors.onPrimary.withValues(alpha: 0.7),
                          width: 1.2,
                        ),
                        borderRadius: AppRadii.allPill,
                      ),
                      child: Text(
                        statusLabel,
                        style: AppTypography.capsLabel.copyWith(
                          color: AppColors.onPrimary,
                          fontSize: 10,
                          letterSpacing: 0.3,
                        ),
                      ),
                    ),
                    const SizedBox(width: AppSpacing.xs),
                    Icon(icon(headerIconName),
                        size: 15, color: AppColors.onPrimary),
                  ],
                ),
              ),
              // ── Body
              Padding(
                padding: const EdgeInsets.fromLTRB(
                    AppSpacing.md, 0, AppSpacing.md, AppSpacing.md),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: <Widget>[
                    if (leftBlock != null || rightBlock != null)
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          if (leftBlock != null) Expanded(child: leftBlock!),
                          Padding(
                            padding: const EdgeInsets.symmetric(
                                horizontal: AppSpacing.xs),
                            child: _TicketConnector(
                              caption: connectorCaption,
                              iconName: connectorIconName,
                            ),
                          ),
                          if (rightBlock != null)
                            Expanded(
                                child: Column(children: <Widget>[rightBlock!])),
                        ],
                      ),
                    if (leftBlock != null || rightBlock != null) ...<Widget>[
                      const SizedBox(height: AppSpacing.md),
                      const DashedDivider(),
                      const SizedBox(height: AppSpacing.md),
                    ],
                    if (keyValues.isNotEmpty || trailingTile != null)
                      IntrinsicHeight(
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.center,
                          children: <Widget>[
                            Expanded(
                              child: IntrinsicHeight(
                                child: Row(
                                  crossAxisAlignment: CrossAxisAlignment.center,
                                  children: <Widget>[
                                    for (int i = 0;
                                        i < keyValues.length;
                                        i++) ...<Widget>[
                                      Expanded(child: keyValues[i]),
                                      if (i < keyValues.length - 1)
                                        Container(
                                          width: 1,
                                          color: AppColors.divider,
                                          margin: const EdgeInsets.symmetric(
                                              horizontal: 6),
                                        ),
                                    ],
                                  ],
                                ),
                              ),
                            ),
                            if (trailingTile != null) ...<Widget>[
                              const SizedBox(width: AppSpacing.sm),
                              trailingTile!,
                            ],
                          ],
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// One column of the boarding-pass route layout.
class TicketRouteBlock extends StatelessWidget {
  const TicketRouteBlock({
    super.key,
    required this.label,
    required this.code,
    this.time,
    this.date,
    this.alignEnd = false,
    this.codeStyle,
  });

  final String label;
  final String code;
  final String? time;
  final String? date;
  final bool alignEnd;
  final TextStyle? codeStyle;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment:
          alignEnd ? CrossAxisAlignment.end : CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        Text(
          label.toUpperCase(),
          style: AppTypography.capsLabel.copyWith(
            color: AppColors.textSecondary,
            fontSize: 10,
            letterSpacing: 0.6,
          ),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        const SizedBox(height: 2),
        Text(
          code,
          style: codeStyle ?? AppTypography.numberLarge,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        if (time != null)
          Text(time!, style: AppTypography.bodyStrong.copyWith(fontSize: 13.5)),
        if (date != null)
          Text(
            date!,
            style: AppTypography.bodyBullet.copyWith(fontSize: 11),
          ),
      ],
    );
  }
}

/// Dotted line with a centred icon and a caption beneath it.
class _TicketConnector extends StatelessWidget {
  const _TicketConnector({this.caption, this.iconName = 'replace'});

  final String? caption;
  final String iconName;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        Container(
          width: 30,
          height: 30,
          decoration: const BoxDecoration(
              color: AppColors.primaryWash, shape: BoxShape.circle),
          alignment: Alignment.center,
          child: Icon(icon(iconName), size: 16, color: AppColors.primary),
        ),
        const SizedBox(height: 4),
        if (caption != null)
          Text(
            caption!,
            style: AppTypography.capsLabel.copyWith(
              color: AppColors.textSecondary,
              fontSize: 9,
              letterSpacing: 0.2,
            ),
            textAlign: TextAlign.center,
          ),
      ],
    );
  }
}

/// Concave rounded transition from the green header into the white body.
class _TicketClipper extends CustomClipper<Path> {
  @override
  Path getClip(Size size) {
    const double radius = AppRadii.lg;
    const double concave = 22;
    const double side = 18;

    final Path path = Path()
      ..addRRect(
        RRect.fromRectAndCorners(
          Offset.zero & size,
          topLeft: const Radius.circular(radius),
          topRight: const Radius.circular(radius),
          bottomLeft: const Radius.circular(radius),
          bottomRight: const Radius.circular(radius),
        ),
      );

    // Punch the concave notches into the left and right edges.
    for (final double x in <double>[0, size.width]) {
      path.addPath(
        Path()
          ..moveTo(x, side + concave)
          ..cubicTo(
            x == 0 ? -side : size.width + side,
            side + concave * 0.15,
            x == 0 ? -side : size.width + side,
            side - concave * 0.15,
            x,
            side - concave,
          )
          ..close(),
        Offset.zero,
      );
    }
    return path;
  }

  @override
  bool shouldReclip(_TicketClipper oldClipper) => false;
}

/// `label` over a bold value — the `Flight` / `Gate` / `Seat` style.
class KeyValueCell extends StatelessWidget {
  const KeyValueCell(
      {super.key, required this.label, required this.value, this.valueColor});

  final String label;
  final String value;
  final Color? valueColor;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        Text(label, style: AppTypography.label.copyWith(fontSize: 11)),
        const SizedBox(height: 1),
        Text(
          value,
          style: AppTypography.bodyStrong
              .copyWith(color: valueColor, fontSize: 13),
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
        ),
      ],
    );
  }
}

/// Plan §6.3: the QR code becomes an **evidence/source link tile** — never a
/// fake QR.
class EvidenceTile extends StatelessWidget {
  const EvidenceTile(
      {super.key, this.onTap, this.label = 'Evidence', this.size = 60});

  final VoidCallback? onTap;
  final String label;
  final double size;

  @override
  Widget build(BuildContext context) {
    return PressScale(
      onTap: onTap,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Container(
            width: size,
            height: size,
            decoration: const BoxDecoration(
              color: AppColors.primarySoft,
              borderRadius: AppRadii.allSm,
            ),
            alignment: Alignment.center,
            child: Icon(icon('fileSearch'),
                size: size * 0.4, color: AppColors.primaryDark),
          ),
          const SizedBox(height: 3),
          Text(
            label,
            style: AppTypography.capsLabel.copyWith(
              color: AppColors.textSecondary,
              fontSize: 8,
              letterSpacing: 0.2,
            ),
          ),
        ],
      ),
    );
  }
}

/// White r 22 card: title row, big number + icon, caption lines.
class MetricCard extends StatelessWidget {
  const MetricCard({
    super.key,
    required this.title,
    this.value,
    this.unit,
    this.caption1,
    this.caption2,
    this.iconName,
    this.statusPill,
    this.onTap,
    this.valueStyle,
    this.accent,
  });

  final String title;
  final String? value;
  final String? unit;
  final String? caption1;
  final String? caption2;
  final String? iconName;
  final Widget? statusPill;
  final VoidCallback? onTap;
  final TextStyle? valueStyle;
  final Color? accent;

  @override
  Widget build(BuildContext context) {
    return SurfaceCard(
      onTap: onTap,
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  title,
                  style: AppTypography.titleCard.copyWith(fontSize: 13.5),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              if (iconName != null)
                Icon(icon(iconName!),
                    size: 26, color: accent ?? AppColors.primarySoft),
            ],
          ),
          if (statusPill != null) ...<Widget>[
            const SizedBox(height: 6),
            statusPill!,
          ],
          if (value != null) ...<Widget>[
            const SizedBox(height: 2),
            Row(
              crossAxisAlignment: CrossAxisAlignment.baseline,
              textBaseline: TextBaseline.alphabetic,
              children: <Widget>[
                Flexible(
                  child: Text(
                    value!,
                    style: valueStyle ?? AppTypography.numberLarge,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                if (unit != null && unit!.isNotEmpty) ...<Widget>[
                  const SizedBox(width: 4),
                  Text(
                    unit!,
                    style: AppTypography.bodyBullet.copyWith(fontSize: 12),
                  ),
                ],
              ],
            ),
          ],
          if (caption1 != null) ...<Widget>[
            const SizedBox(height: 4),
            Text(
              caption1!,
              style: AppTypography.bodyBullet.copyWith(fontSize: 11.5),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ],
          if (caption2 != null)
            Text(
              caption2!,
              style: AppTypography.caption.copyWith(fontSize: 10.5),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
        ],
      ),
    );
  }
}

/// White r 22; 64 px ring, bold % + caption.
class ProgressRingCard extends StatelessWidget {
  const ProgressRingCard({
    super.key,
    required this.title,
    required this.progress,
    required this.caption,
    this.valueLabel,
    this.glyph = 'shieldCheck',
    this.onTap,
    this.accent,
  });

  final String title;
  final double progress;
  final String caption;
  final String? valueLabel;
  final String glyph;
  final VoidCallback? onTap;
  final Color? accent;

  @override
  Widget build(BuildContext context) {
    return SurfaceCard(
      onTap: onTap,
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Text(
            title,
            style: AppTypography.titleCard.copyWith(fontSize: 13.5),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: AppSpacing.xs),
          Row(
            children: <Widget>[
              ProgressRing(
                progress: progress,
                size: 56,
                stroke: 6,
                color: accent,
                child: Icon(icon(glyph),
                    size: 20, color: accent ?? AppColors.primary),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    if (valueLabel != null)
                      Text(
                        valueLabel!,
                        style: AppTypography.numberLargeSans
                            .copyWith(fontSize: 22),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    Text(
                      caption,
                      style: AppTypography.bodyBullet.copyWith(fontSize: 11.5),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

/// Title + count + chevron, rounded progress bar, two-column items with 18 px
/// circles (filled-green check / empty outline).
class ChecklistCard extends StatelessWidget {
  const ChecklistCard({
    super.key,
    required this.title,
    required this.items,
    this.countLabel,
    this.onHeaderTap,
    this.onItemToggle,
    this.columns = 2,
    this.progress,
  });

  final String title;
  final List<ChecklistItemModel> items;
  final String? countLabel;
  final VoidCallback? onHeaderTap;
  // ignore: avoid_positional_boolean_parameters — callback signature mirrors `onChanged`.
  final void Function(ChecklistItemModel item, bool value)? onItemToggle;
  final int columns;
  final double? progress;

  @override
  Widget build(BuildContext context) {
    final int done = items.where((ChecklistItemModel i) => i.done).length;
    return SurfaceCard(
      padding: const EdgeInsets.all(AppSpacing.md),
      onTap: onHeaderTap,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                  child: Text(title,
                      style: AppTypography.titleCard.copyWith(fontSize: 14.5))),
              if (countLabel != null)
                Text(countLabel!,
                    style: AppTypography.bodyBullet.copyWith(fontSize: 11.5)),
              if (onHeaderTap != null) ...<Widget>[
                const SizedBox(width: 4),
                Icon(AppIcons.byName('chevronRight'),
                    size: 16, color: AppColors.textTertiary),
              ],
            ],
          ),
          const SizedBox(height: AppSpacing.xs),
          ProgressBar(
              value: progress ?? (items.isEmpty ? 0 : done / items.length)),
          const SizedBox(height: AppSpacing.sm),
          LayoutBuilder(
            builder: (BuildContext context, BoxConstraints constraints) {
              final int cols = columns;
              final double itemWidth =
                  (constraints.maxWidth - AppSpacing.xs * (cols - 1)) / cols;
              return Wrap(
                spacing: AppSpacing.xs,
                runSpacing: AppSpacing.xs,
                children: <Widget>[
                  for (final ChecklistItemModel item in items)
                    SizedBox(
                      width: itemWidth,
                      child: PressScale(
                        onTap: onItemToggle == null
                            ? null
                            : () => onItemToggle!(item, !item.done),
                        scale: 0.97,
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: <Widget>[
                            _CheckCircle(done: item.done, size: 18),
                            const SizedBox(width: 6),
                            Expanded(
                              child: Text(
                                item.label,
                                style: AppTypography.bodyBullet.copyWith(
                                  fontSize: 11.5,
                                  color: item.done
                                      ? AppColors.textTertiary
                                      : AppColors.textPrimary,
                                  decoration: item.done
                                      ? TextDecoration.lineThrough
                                      : null,
                                  decorationColor: AppColors.textTertiary,
                                ),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}

class ChecklistItemModel {
  const ChecklistItemModel(
      {required this.id, required this.label, this.done = false, this.detail});

  final String id;
  final String label;
  final bool done;
  final String? detail;

  ChecklistItemModel copyWith({bool? done}) => ChecklistItemModel(
        id: id,
        label: label,
        done: done ?? this.done,
        detail: detail,
      );
}

class _CheckCircle extends StatelessWidget {
  const _CheckCircle({required this.done, this.size = 18});

  final bool done;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: done ? AppColors.primary : Colors.transparent,
        shape: BoxShape.circle,
        border: done
            ? null
            : Border.all(color: AppColors.dividerStrong, width: 1.4),
      ),
      alignment: Alignment.center,
      child: done
          ? Icon(
              LucideIcons.check,
              size: size * 0.6,
              color: AppColors.onPrimary,
            )
          : null,
    );
  }
}

/// Source row + quoted `source_text` in `surfaceTint` with the exact span
/// highlighted, page chip, confidence badge.
class EvidenceCard extends StatelessWidget {
  const EvidenceCard({
    super.key,
    required this.sourceTitle,
    required this.sourceMeta,
    this.pageChip,
    this.verbatim,
    this.highlight,
    this.confidenceBand,
    this.confidence,
    this.provenanceVerified = false,
    this.onOpenSource,
    this.emptyMessage,
  });

  final String sourceTitle;
  final String sourceMeta;
  final String? pageChip;
  final String? verbatim;

  /// The exact substring inside [verbatim] that produced the fact.
  final String? highlight;
  final ConfidenceBand? confidenceBand;
  final double? confidence;
  final bool provenanceVerified;
  final VoidCallback? onOpenSource;
  final String? emptyMessage;

  @override
  Widget build(BuildContext context) {
    final String? text = verbatim;
    return SurfaceCard(
      padding: EdgeInsets.zero,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Padding(
            padding: const EdgeInsets.all(AppSpacing.cardGap),
            child: Row(
              children: <Widget>[
                ClipRRect(
                  borderRadius: AppRadii.allSm,
                  child: Container(
                    width: 52,
                    height: 52,
                    decoration:
                        const BoxDecoration(gradient: AppColors.monogram),
                    alignment: Alignment.center,
                    child: Icon(icon('fileText'),
                        size: 20, color: AppColors.primaryDark),
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      Text(
                        sourceTitle,
                        style: AppTypography.titleCard.copyWith(fontSize: 14),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 2),
                      Text(
                        sourceMeta,
                        style: AppTypography.bodyBullet.copyWith(fontSize: 11),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: AppSpacing.xs),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    if (pageChip != null)
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 4),
                        decoration: const BoxDecoration(
                          color: AppColors.surfaceTint,
                          borderRadius: AppRadii.allPill,
                        ),
                        child: Text(pageChip!,
                            style:
                                AppTypography.capsLabel.copyWith(fontSize: 9)),
                      ),
                    if (onOpenSource != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 6),
                        child: GestureDetector(
                          onTap: onOpenSource,
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: <Widget>[
                              Icon(icon('externalLink'),
                                  size: 12, color: AppColors.primary),
                              const SizedBox(width: 3),
                              Text('Open',
                                  style: AppTypography.link
                                      .copyWith(fontSize: 11)),
                            ],
                          ),
                        ),
                      ),
                  ],
                ),
              ],
            ),
          ),
          if (confidenceBand != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(
                  AppSpacing.cardGap, 0, AppSpacing.cardGap, AppSpacing.xs),
              child: Row(
                children: <Widget>[
                  ConfidenceBadge(band: confidenceBand!, score: confidence),
                  const SizedBox(width: 6),
                  if (provenanceVerified)
                    const StatusPill(
                      label: 'Provenance verified',
                      variant: StatusPillVariant.approved,
                      icon: 'shieldCheck',
                      dense: true,
                    ),
                ],
              ),
            ),
          if (text == null || text.trim().isEmpty)
            Padding(
              padding: const EdgeInsets.all(AppSpacing.cardGap),
              child: ClinNoticeBanner(
                message:
                    emptyMessage ?? 'Source text unavailable for this fact.',
                tone: ClinNoticeTone.neutral,
                icon: 'fileWarning',
              ),
            )
          else
            Container(
              margin: const EdgeInsets.fromLTRB(AppSpacing.cardGap, 0,
                  AppSpacing.cardGap, AppSpacing.cardGap),
              padding: const EdgeInsets.all(AppSpacing.sm),
              decoration: const BoxDecoration(
                color: AppColors.surfaceTint,
                borderRadius: AppRadii.allMd,
              ),
              child: _HighlightedText(
                text: text,
                highlight: highlight,
              ),
            ),
        ],
      ),
    );
  }
}

class _HighlightedText extends StatelessWidget {
  const _HighlightedText({required this.text, this.highlight});

  final String text;
  final String? highlight;

  @override
  Widget build(BuildContext context) {
    final String? needle = highlight;
    if (needle == null || needle.trim().isEmpty || !text.contains(needle)) {
      return Text(text, style: AppTypography.verbatim);
    }
    final int index = text.indexOf(needle);
    return RichText(
      text: TextSpan(
        style: AppTypography.verbatim,
        children: <InlineSpan>[
          TextSpan(text: text.substring(0, index)),
          TextSpan(
            text: text.substring(index, index + needle.length),
            style: AppTypography.verbatim.copyWith(
              backgroundColor: AppColors.primarySoft,
              color: AppColors.primaryDark,
              fontWeight: FontWeight.w500,
            ),
          ),
          TextSpan(text: text.substring(index + needle.length)),
        ],
      ),
    );
  }
}

/// A small inline chip that opens Evidence — used on every brief statement
/// (plan §9.14 "every line has a tiny evidence chip").
class EvidenceChip extends StatelessWidget {
  const EvidenceChip(
      {super.key,
      this.onTap,
      this.label = 'Evidence',
      this.iconName = 'fileSearch'});

  final VoidCallback? onTap;
  final String label;
  final String iconName;

  @override
  Widget build(BuildContext context) {
    return PressScale(
      onTap: onTap,
      scale: 0.94,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
        decoration: const BoxDecoration(
          color: AppColors.primarySoft,
          borderRadius: AppRadii.allPill,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Icon(icon(iconName), size: 10, color: AppColors.primaryDark),
            if (label.isNotEmpty) ...<Widget>[
              const SizedBox(width: 3),
              Text(
                label,
                style: AppTypography.capsLabel.copyWith(
                  color: AppColors.primaryDark,
                  fontSize: 8.5,
                  letterSpacing: 0.2,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Small labelled section used inside the Brief (plan §9.14 "compact section
/// cards").
class BriefSectionCard extends StatelessWidget {
  const BriefSectionCard({
    super.key,
    required this.title,
    required this.child,
    this.trailing,
    this.iconName,
  });

  final String title;
  final Widget child;
  final Widget? trailing;
  final String? iconName;

  @override
  Widget build(BuildContext context) {
    return SurfaceCard(
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              if (iconName != null) ...<Widget>[
                Icon(icon(iconName!), size: 15, color: AppColors.primary),
                const SizedBox(width: 6),
              ],
              Expanded(
                child: Text(
                  title,
                  style: AppTypography.capsLabel.copyWith(
                    color: AppColors.textSecondary,
                    fontSize: 10.5,
                  ),
                ),
              ),
              if (trailing != null) trailing!,
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          child,
        ],
      ),
    );
  }
}

/// A dated timeline event rendered as `TimelineRail` + `TimelineCard`.
class DatedTimelineEntry extends StatelessWidget {
  const DatedTimelineEntry({
    super.key,
    required this.child,
    required this.date,
    this.isFirst = false,
    this.isLast = false,
    this.pulsing = false,
  });

  final Widget child;
  final Object? date;
  final bool isFirst;
  final bool isLast;
  final bool pulsing;

  @override
  Widget build(BuildContext context) {
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          TimelineRail(
            label: AppDate.capsMonth(date),
            number: AppDate.dayNumber(date),
            isFirst: isFirst,
            isLast: isLast,
            pulsing: pulsing,
          ),
          const SizedBox(width: AppSpacing.xs),
          Expanded(child: child),
        ],
      ),
    );
  }
}
