import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/animations/motion.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_radii.dart';
import '../../core/theme/app_shadows.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/utils/confidence_band.dart';
import 'app_icons.dart';

/// 44 px white circle, `shadowCard`, 20 px line icon — plan §7.6.
class CircleIconButton extends StatelessWidget {
  const CircleIconButton({
    super.key,
    this.icon,
    this.iconData,
    this.onTap,
    this.tooltip,
    this.filled = false,
    this.size = 44,
    this.iconSize = 20,
    this.color,
    this.background,
    this.borderColor,
    this.enabled = true,
  });

  /// A `LucideIcons` member name, or an explicit [iconData].
  final String? icon;
  final IconData? iconData;
  final VoidCallback? onTap;
  final String? tooltip;

  /// Green filled variant (used for the mic).
  final bool filled;
  final double size;
  final double iconSize;
  final Color? color;
  final Color? background;
  final Color? borderColor;
  final bool enabled;

  IconData get _icon => iconData ?? _resolve(icon ?? 'circle');

  @override
  Widget build(BuildContext context) {
    final fg = !enabled
        ? AppColors.textDisabled
        : filled
            ? AppColors.onPrimary
            : (color ?? AppColors.textPrimary);
    final bg = !enabled
        ? AppColors.surfaceTint
        : filled
            ? AppColors.primary
            : (background ?? AppColors.surface);

    Widget button = Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: bg,
        shape: BoxShape.circle,
        boxShadow: enabled && onTap != null ? AppShadows.card : null,
        border: borderColor == null
            ? null
            : Border.all(color: borderColor!, width: 1.4),
      ),
      alignment: Alignment.center,
      child: Icon(_icon, size: iconSize, color: fg),
    );

    button = PressScale(onTap: enabled ? onTap : null, child: button);
    if (tooltip != null) {
      button = Tooltip(message: tooltip!, child: button);
    }
    return button;
  }
}

/// Height 56, full pill, `primary`, white icon + text — plan §7.6.
class PrimaryPillButton extends StatelessWidget {
  const PrimaryPillButton({
    super.key,
    required this.label,
    this.onPressed,
    this.icon,
    this.iconData,
    this.expand = true,
    this.height = 56,
    this.enabled = true,
    this.tooltip,
  });

  final String label;
  final VoidCallback? onPressed;

  /// A `LucideIcons` member name, or an explicit [iconData].
  final String? icon;
  final IconData? iconData;
  final bool expand;
  final double height;
  final bool enabled;
  final String? tooltip;

  @override
  Widget build(BuildContext context) {
    final active = enabled && onPressed != null;
    Widget button = AnimatedOpacity(
      duration: const Duration(milliseconds: 160),
      opacity: enabled ? 1 : 0.4,
      child: Container(
        height: height,
        width: expand ? double.infinity : null,
        padding: expand
            ? null
            : const EdgeInsets.symmetric(horizontal: AppSpacing.xl),
        decoration: BoxDecoration(
          color: AppColors.primary,
          borderRadius: AppRadii.allPill,
          boxShadow: active ? AppShadows.button : null,
        ),
        child: Row(
          mainAxisSize: expand ? MainAxisSize.max : MainAxisSize.min,
          mainAxisAlignment: MainAxisAlignment.center,
          children: <Widget>[
            if (icon != null || iconData != null) ...<Widget>[
              Icon(
                iconData ?? _resolve(icon!),
                size: 20,
                color: AppColors.onPrimary,
              ),
              const SizedBox(width: AppSpacing.xs),
            ],
            Flexible(
              child: Text(
                label,
                style: AppTypography.button,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ),
    );

    button = PressScale(
      onTap: active ? onPressed : null,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 120),
        decoration: const BoxDecoration(),
        child: button,
      ),
    );

    if (tooltip != null) {
      button = Tooltip(message: tooltip!, child: button);
    }
    return button;
  }
}

/// Left `titleSection`, optional right `link` — plan §7.6.
class SectionHeader extends StatelessWidget {
  const SectionHeader({
    super.key,
    required this.title,
    this.linkLabel,
    this.onLinkTap,
    this.padding = const EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
  });

  final String title;
  final String? linkLabel;
  final VoidCallback? onLinkTap;
  final EdgeInsets padding;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: padding,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: <Widget>[
          Expanded(child: Text(title, style: AppTypography.titleSection)),
          if (linkLabel != null)
            PressScale(
              onTap: onLinkTap,
              child: Padding(
                padding: const EdgeInsets.only(
                    left: AppSpacing.xs, top: 4, bottom: 4),
                child: Text(linkLabel!, style: AppTypography.link),
              ),
            ),
        ],
      ),
    );
  }
}

/// Height 56 white pill, leading search icon, trailing filled-green mic —
/// plan §7.6.
class SearchPill extends StatelessWidget {
  const SearchPill({
    super.key,
    required this.hint,
    this.onTap,
    this.onChanged,
    this.controller,
    this.focusNode,
    this.autofocus = false,
    this.onMicTap,
    this.textInputAction,
  });

  final String hint;
  final VoidCallback? onTap;
  final ValueChanged<String>? onChanged;
  final TextEditingController? controller;
  final FocusNode? focusNode;
  final bool autofocus;
  final VoidCallback? onMicTap;
  final TextInputAction? textInputAction;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 56,
      decoration: const BoxDecoration(
        color: AppColors.surface,
        borderRadius: AppRadii.allPill,
        boxShadow: AppShadows.float,
      ),
      padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.xs, 0),
      child: Row(
        children: <Widget>[
          const Icon(LucideIcons.search,
              size: 20, color: AppColors.textSecondary),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: onChanged == null
                ? PressScale(
                    onTap: onTap,
                    child: Align(
                      alignment: Alignment.centerLeft,
                      child: Text(
                        hint,
                        style: AppTypography.body
                            .copyWith(color: AppColors.textTertiary),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  )
                : TextField(
                    controller: controller,
                    focusNode: focusNode,
                    autofocus: autofocus,
                    onChanged: onChanged,
                    textInputAction: textInputAction,
                    style: AppTypography.body,
                    cursorColor: AppColors.primary,
                    cursorWidth: 1.6,
                    decoration: InputDecoration(
                      isDense: true,
                      filled: false,
                      border: InputBorder.none,
                      enabledBorder: InputBorder.none,
                      focusedBorder: InputBorder.none,
                      contentPadding: EdgeInsets.zero,
                      hintText: hint,
                      hintStyle: AppTypography.body
                          .copyWith(color: AppColors.textTertiary),
                    ),
                  ),
          ),
          const SizedBox(width: AppSpacing.xs),
          CircleIconButton(
              icon: 'mic', filled: true, onTap: onMicTap, size: 44),
        ],
      ),
    );
  }
}

/// 3 dots; active = `primary`, inactive = `divider` — plan §7.6.
class PageDots extends StatelessWidget {
  const PageDots(
      {super.key, required this.count, required this.activeIndex, this.onTap});

  final int count;
  final int activeIndex;
  final ValueChanged<int>? onTap;

  @override
  Widget build(BuildContext context) {
    if (count <= 1) return const SizedBox(height: 6);
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: <Widget>[
        for (int i = 0; i < count; i++)
          GestureDetector(
            onTap: onTap == null ? null : () => onTap!(i),
            behavior: HitTestBehavior.opaque,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 3, vertical: 6),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 220),
                width: i == activeIndex ? 7 : 6,
                height: 6,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: i == activeIndex
                      ? AppColors.primary
                      : AppColors.dividerStrong,
                ),
              ),
            ),
          ),
      ],
    );
  }
}

/// Pill, 11/600, clinical-status variants — plan §7.6 / §6.6.
enum StatusPillVariant {
  /// `AI-generated · Unverified`
  aiGenerated,

  /// `Doctor approved`
  approved,

  /// `Review`
  needsReview,

  /// `Conflict`
  conflict,

  /// `Demo data` (fallback)
  demo,

  /// Neutral metadata chip.
  neutral,
}

/// 11/600 pill. Colour is the only signal; text always carries the meaning.
class StatusPill extends StatelessWidget {
  const StatusPill({
    super.key,
    required this.label,
    this.variant = StatusPillVariant.neutral,
    this.icon,
    this.dense = false,
  });

  final String label;
  final StatusPillVariant variant;
  final String? icon;
  final bool dense;

  @override
  Widget build(BuildContext context) {
    final (Color fg, Color bg) = switch (variant) {
      StatusPillVariant.aiGenerated => (
          AppColors.primaryDark,
          AppColors.primarySoft
        ),
      StatusPillVariant.approved => (AppColors.onPrimary, AppColors.primary),
      StatusPillVariant.needsReview => (
          AppColors.warning,
          AppColors.warningSoft
        ),
      StatusPillVariant.conflict => (AppColors.danger, AppColors.dangerSoft),
      StatusPillVariant.demo => (
          AppColors.textSecondary,
          AppColors.surfaceTint
        ),
      StatusPillVariant.neutral => (
          AppColors.textSecondary,
          AppColors.surfaceTint
        ),
    };

    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: dense ? AppSpacing.xs : 10,
        vertical: dense ? 3 : 5,
      ),
      decoration: BoxDecoration(color: bg, borderRadius: AppRadii.allPill),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          if (icon != null) ...<Widget>[
            Icon(_resolve(icon!), size: dense ? 11 : 12, color: fg),
            const SizedBox(width: 4),
          ],
          Text(
            label,
            style: AppTypography.capsLabel.copyWith(
              color: fg,
              fontSize: dense ? 9.5 : 10.5,
              letterSpacing: 0.4,
            ),
          ),
        ],
      ),
    );
  }
}

/// Small pill + 3-segment micro-bar showing `High / Medium / Needs
/// verification` — plan §7.6 / §6.6 rule 2.
class ConfidenceBadge extends StatelessWidget {
  const ConfidenceBadge({
    super.key,
    required this.band,
    this.score,
    this.dense = false,
  });

  final ConfidenceBand band;
  final double? score;
  final bool dense;

  Color get _color => switch (band) {
        ConfidenceBand.high => AppColors.confidenceHigh,
        ConfidenceBand.medium => AppColors.confidenceMedium,
        ConfidenceBand.needsVerification => AppColors.confidenceLow,
      };

  @override
  Widget build(BuildContext context) {
    final label = score == null
        ? band.label
        : '${band.label} · ${(score! * 100).round()}%';
    return Tooltip(
      message: 'Extraction confidence ${band.threshold}',
      child: Container(
        padding: EdgeInsets.symmetric(
          horizontal: dense ? 6 : 8,
          vertical: dense ? 3 : 4,
        ),
        decoration: BoxDecoration(
          color: _color.withValues(alpha: 0.10),
          borderRadius: AppRadii.allPill,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            // 3-segment micro-bar.
            Row(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                for (int i = 0; i < 3; i++)
                  Container(
                    width: 3,
                    height: 8,
                    margin: const EdgeInsets.only(right: 1.5),
                    decoration: BoxDecoration(
                      color: i < band.filledSegments
                          ? _color
                          : AppColors.confidenceTrack,
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
              ],
            ),
            const SizedBox(width: 5),
            Text(
              label,
              style: AppTypography.capsLabel.copyWith(
                color: _color,
                fontSize: dense ? 9 : 10,
                letterSpacing: 0.2,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Animated circular progress with a centre glyph — plan §7.6.
class ProgressRing extends StatelessWidget {
  const ProgressRing({
    super.key,
    required this.progress,
    this.size = 64,
    this.stroke = 7,
    this.color,
    this.trackColor,
    this.child,
    this.duration = const Duration(milliseconds: 700),
  });

  /// 0..1
  final double progress;
  final double size;
  final double stroke;
  final Color? color;
  final Color? trackColor;
  final Widget? child;
  final Duration duration;

  @override
  Widget build(BuildContext context) {
    final reduce = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    return SizedBox(
      width: size,
      height: size,
      child: Stack(
        alignment: Alignment.center,
        children: <Widget>[
          TweenAnimationBuilder<double>(
            tween: Tween<double>(begin: 0, end: progress.clamp(0.0, 1.0)),
            duration: reduce ? const Duration(milliseconds: 100) : duration,
            curve: Curves.easeOutCubic,
            builder: (BuildContext context, double v, Widget? _) {
              return CustomPaint(
                size: Size(size, size),
                painter: _RingPainter(
                  value: v,
                  stroke: stroke,
                  color: color ?? AppColors.primary,
                  trackColor: trackColor ?? AppColors.surfaceTint,
                ),
              );
            },
          ),
          if (child != null) child!,
        ],
      ),
    );
  }
}

class _RingPainter extends CustomPainter {
  _RingPainter(
      {required this.value,
      required this.stroke,
      required this.color,
      required this.trackColor});

  final double value;
  final double stroke;
  final Color color;
  final Color trackColor;

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    final centre = rect.center;
    final radius = (size.shortestSide - stroke) / 2;

    final track = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.round
      ..color = trackColor;
    canvas.drawCircle(centre, radius, track);

    if (value <= 0) return;
    final arc = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.round
      ..color = color;
    canvas.drawArc(
      Rect.fromCircle(center: centre, radius: radius),
      -1.5707963,
      6.2831853 * value,
      false,
      arc,
    );
  }

  @override
  bool shouldRepaint(_RingPainter old) =>
      old.value != value || old.color != color || old.stroke != stroke;
}

/// Rounded 6 px progress bar — plan §7.6.
class ProgressBar extends StatelessWidget {
  const ProgressBar({
    super.key,
    required this.value,
    this.height = 6,
    this.color,
    this.trackColor,
  });

  final double value;
  final double height;
  final Color? color;
  final Color? trackColor;

  @override
  Widget build(BuildContext context) {
    final reduce = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    return ClipRRect(
      borderRadius: BorderRadius.circular(height),
      child: Container(
        height: height,
        color: trackColor ?? AppColors.surfaceTint,
        child: Align(
          alignment: Alignment.centerLeft,
          child: TweenAnimationBuilder<double>(
            tween: Tween<double>(begin: 0, end: value.clamp(0.0, 1.0)),
            duration: reduce
                ? const Duration(milliseconds: 100)
                : const Duration(milliseconds: 700),
            curve: Curves.easeOutCubic,
            builder: (BuildContext context, double v, Widget? _) {
              return FractionallySizedBox(
                widthFactor: v,
                child: Container(color: color ?? AppColors.primary),
              );
            },
          ),
        ),
      ),
    );
  }
}

/// The base elevated white surface used by every card.
class SurfaceCard extends StatelessWidget {
  const SurfaceCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(AppSpacing.cardGap),
    this.radius = AppRadii.lg,
    this.onTap,
    this.color,
    this.borderColor,
    this.elevated = true,
    this.accentLeft = false,
  });

  final Widget child;
  final EdgeInsets padding;
  final double radius;
  final VoidCallback? onTap;
  final Color? color;
  final Color? borderColor;
  final bool elevated;

  /// 3 px `primary` accent on the left edge (verified memory cards).
  final bool accentLeft;

  @override
  Widget build(BuildContext context) {
    Widget card = Container(
      decoration: BoxDecoration(
        color: color ?? AppColors.surface,
        borderRadius: BorderRadius.circular(radius),
        boxShadow: elevated ? AppShadows.card : null,
        border: borderColor == null
            ? null
            : Border.all(color: borderColor!, width: 1),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(radius),
        // `IntrinsicHeight` is only needed for the left accent, and it forces an
        // intrinsic pass over the whole subtree. `LayoutBuilder` cannot supply
        // intrinsic dimensions, so the default path must not use it — otherwise
        // `ChecklistCard` and any other intrinsic-free card would throw.
        child: accentLeft
            ? IntrinsicHeight(
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: <Widget>[
                    Container(width: 3, color: AppColors.primary),
                    Expanded(
                      child: Padding(
                        padding: padding.copyWith(left: padding.left - 1),
                        child: child,
                      ),
                    ),
                  ],
                ),
              )
            : Padding(padding: padding, child: child),
      ),
    );
    if (onTap != null) {
      card = PressScale(onTap: onTap, child: card);
    }
    return card;
  }
}

/// 28 px outline circle with `+` and `link`-style text — plan §7.6.
class AddRow extends StatelessWidget {
  const AddRow(
      {super.key, required this.label, this.onTap, this.icon = 'plus'});

  final String label;
  final VoidCallback? onTap;
  final String icon;

  @override
  Widget build(BuildContext context) {
    return PressScale(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(
            vertical: AppSpacing.sm, horizontal: AppSpacing.xs),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Container(
              width: 28,
              height: 28,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                border: Border.all(color: AppColors.dividerStrong, width: 1.4),
              ),
              alignment: Alignment.center,
              child:
                  Icon(_resolve(icon), size: 15, color: AppColors.textPrimary),
            ),
            const SizedBox(width: AppSpacing.sm),
            Text(label, style: AppTypography.link),
          ],
        ),
      ),
    );
  }
}

/// Overlapping 28 px circles with a white 2 px ring, plus a `+N` chip.
/// In ClinSync these are document-type glyph circles (plan §6.3) — never
/// patient photographs.
class AvatarStack extends StatelessWidget {
  const AvatarStack({
    super.key,
    required this.items,
    this.size = 28,
    this.max = 3,
    this.onOverflowTap,
    this.overflowExtra = 0,
  });

  /// Icon names, resolved through `AppIcons.table`.
  final List<String> items;
  final double size;
  final int max;
  final VoidCallback? onOverflowTap;

  /// Extra count for the `+N` chip when the caller knows the true total (e.g. a
  /// patient's document count) instead of the truncated list length.
  final int overflowExtra;

  @override
  Widget build(BuildContext context) {
    final shown = items.take(max).toList(growable: false);
    final overflow =
        overflowExtra > 0 ? overflowExtra : items.length - shown.length;
    return SizedBox(
      height: size,
      child: Stack(
        children: <Widget>[
          for (int i = 0; i < shown.length; i++)
            Positioned(
              left: i * (size * 0.66),
              child: Container(
                width: size,
                height: size,
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  shape: BoxShape.circle,
                  border: Border.all(color: AppColors.surface, width: 2),
                  boxShadow: AppShadows.tile,
                ),
                alignment: Alignment.center,
                child: Icon(_resolve(shown[i]),
                    size: size * 0.46, color: AppColors.primary),
              ),
            ),
          if (overflow > 0)
            Positioned(
              left: shown.length * (size * 0.66),
              child: PressScale(
                onTap: onOverflowTap,
                child: Container(
                  height: size,
                  padding: EdgeInsets.symmetric(horizontal: size > 30 ? 8 : 6),
                  decoration: BoxDecoration(
                    color: AppColors.surface,
                    shape: BoxShape.circle,
                    border: Border.all(color: AppColors.surface, width: 2),
                    boxShadow: AppShadows.tile,
                  ),
                  alignment: Alignment.center,
                  child: Text(
                    '+$overflow',
                    style: AppTypography.caption.copyWith(
                      fontWeight: FontWeight.w600,
                      color: AppColors.textSecondary,
                      fontSize: 10.5,
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

/// Row: leading `CircleIconButton`, centred `titleScreen` (+ grey sub-line),
/// trailing 1–2 buttons. Transparent over canvas — plan §7.6.
class TopBar extends StatelessWidget {
  const TopBar({
    super.key,
    this.title,
    this.subtitle,
    this.leadingIcon = 'arrowLeft',
    this.leadingIconData,
    this.onLeadingTap,
    this.trailing = const <Widget>[],
    this.showLeading = true,
    this.padding = const EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
    this.bottom,
  });

  final String? title;
  final String? subtitle;
  final String? leadingIcon;
  final IconData? leadingIconData;
  final VoidCallback? onLeadingTap;
  final List<Widget> trailing;
  final bool showLeading;
  final EdgeInsets padding;
  final Widget? bottom;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: <Widget>[
        Padding(
          padding: EdgeInsets.only(
            left: showLeading ? AppSpacing.screenH : AppSpacing.screenH,
            right: AppSpacing.screenH,
            top: AppSpacing.xs,
          ),
          child: Row(
            children: <Widget>[
              if (showLeading)
                CircleIconButton(
                  icon: leadingIcon,
                  iconData: leadingIconData,
                  onTap: onLeadingTap,
                )
              else
                const SizedBox(width: AppSpacing.xxl),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    if (title != null)
                      Text(
                        title!,
                        style: AppTypography.titleScreen,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    if (subtitle != null)
                      Text(
                        subtitle!,
                        style: AppTypography.titleScreenSub,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                  ],
                ),
              ),
              const SizedBox(width: AppSpacing.xs),
              ...trailing,
            ],
          ),
        ),
        if (bottom != null) bottom!,
      ],
    );
  }
}

/// Row; selected = `primary` pill with white text, unselected = plain grey —
/// plan §7.6. Horizontally scrollable when it overflows.
class PillTabs extends StatelessWidget {
  const PillTabs({
    super.key,
    required this.labels,
    required this.selectedIndex,
    required this.onChanged,
    this.padding = const EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
  });

  final List<String> labels;
  final int selectedIndex;
  final ValueChanged<int> onChanged;
  final EdgeInsets padding;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: padding,
      physics: const BouncingScrollPhysics(),
      child: Row(
        children: <Widget>[
          for (int i = 0; i < labels.length; i++)
            Padding(
              padding: EdgeInsets.only(
                  right: i == labels.length - 1 ? 0 : AppSpacing.xs),
              child: PressScale(
                onTap: () => onChanged(i),
                scale: 0.96,
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 220),
                  curve: Curves.easeOutCubic,
                  padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.md, vertical: 9),
                  decoration: BoxDecoration(
                    color: i == selectedIndex
                        ? AppColors.primary
                        : Colors.transparent,
                    borderRadius: AppRadii.allPill,
                  ),
                  child: Text(
                    labels[i],
                    style: AppTypography.tabLabel.copyWith(
                      color: i == selectedIndex
                          ? AppColors.onPrimary
                          : AppColors.textSecondary,
                      fontWeight: i == selectedIndex
                          ? FontWeight.w600
                          : FontWeight.w500,
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

/// Bottom bar over canvas with top fade: `PrimaryPillButton` (flex) +
/// 56 px `CircleIconButton` — plan §7.6.
class StickyActionBar extends StatelessWidget {
  const StickyActionBar({
    super.key,
    required this.primaryLabel,
    required this.onPrimary,
    this.primaryIcon,
    this.primaryIconData,
    this.secondaryIcon,
    this.secondaryIconData,
    this.onSecondary,
    this.enabled = true,
    this.tooltip,
    this.secondaryTooltip,
    this.extraSecondaryIcons = const <Widget>[],
  });

  final String primaryLabel;
  final VoidCallback? onPrimary;
  final String? primaryIcon;
  final IconData? primaryIconData;
  final String? secondaryIcon;
  final IconData? secondaryIconData;
  final VoidCallback? onSecondary;
  final bool enabled;

  /// Shown when the primary action is disabled.
  final String? tooltip;
  final String? secondaryTooltip;
  final List<Widget> extraSecondaryIcons;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.fromLTRB(
        AppSpacing.screenH,
        AppSpacing.sm,
        AppSpacing.screenH,
        MediaQuery.paddingOf(context).bottom + AppSpacing.sm,
      ),
      decoration: BoxDecoration(
        color: AppColors.bgCanvas.withValues(alpha: 0.96),
        boxShadow: <BoxShadow>[
          BoxShadow(
            color: AppColors.divider.withValues(alpha: 0.55),
            blurRadius: 18,
            offset: const Offset(0, -6),
            spreadRadius: -6,
          ),
        ],
      ),
      child: Row(
        children: <Widget>[
          Expanded(
            child: PrimaryPillButton(
              label: primaryLabel,
              icon: primaryIcon,
              iconData: primaryIconData,
              onPressed: onPrimary,
              enabled: enabled,
              tooltip: tooltip,
            ),
          ),
          if (secondaryIcon != null || secondaryIconData != null) ...<Widget>[
            const SizedBox(width: AppSpacing.sm),
            CircleIconButton(
              icon: secondaryIcon,
              iconData: secondaryIconData,
              onTap: onSecondary,
              tooltip: secondaryTooltip,
              size: 56,
              iconSize: 22,
            ),
          ],
          ...extraSecondaryIcons,
        ],
      ),
    );
  }
}

/// A dashed horizontal rule — used by `TicketCard` and evidence cards.
class DashedDivider extends StatelessWidget {
  const DashedDivider(
      {super.key, this.color, this.height = 1, this.dash = 4, this.gap = 4});

  final Color? color;
  final double height;
  final double dash;
  final double gap;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: height,
      width: double.infinity,
      child: CustomPaint(
        painter: _DashPainter(color ?? AppColors.divider, dash, gap),
      ),
    );
  }
}

class _DashPainter extends CustomPainter {
  _DashPainter(this.color, this.dash, this.gap);

  final Color color;
  final double dash;
  final double gap;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = size.height;
    final y = size.height / 2;
    var x = 0.0;
    while (x < size.width) {
      canvas.drawLine(
          Offset(x, y), Offset((x + dash).clamp(0, size.width), y), paint);
      x += dash + gap;
    }
  }

  @override
  bool shouldRepaint(_DashPainter old) =>
      old.color != color || old.dash != dash || old.gap != gap;
}

/// Resolves a named icon to an [IconData]; unknown names fall back to a circle.
IconData _resolve(String name) => AppIcons.byName(name);
