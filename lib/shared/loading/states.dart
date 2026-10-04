import 'package:flutter/material.dart';

import '../../core/theme/app_colors.dart';
import '../../core/theme/app_radii.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../widgets/app_icons.dart';
import '../widgets/primitives.dart';

/// Shimmer in `surfaceTint` — plan §11.5.
class _Shimmer extends StatefulWidget {
  const _Shimmer({required this.child, this.radius = AppRadii.allMd});

  final Widget child;
  final BorderRadius radius;

  @override
  State<_Shimmer> createState() => _ShimmerState();
}

class _ShimmerState extends State<_Shimmer>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1200),
  )..repeat();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final reduce = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    if (reduce) return widget.child;
    return AnimatedBuilder(
      animation: _controller,
      builder: (BuildContext context, Widget? child) {
        return ShaderMask(
          blendMode: BlendMode.srcATop,
          shaderCallback: (Rect bounds) {
            final double t = _controller.value;
            return LinearGradient(
              begin: Alignment(-1 - 2 * (1 - t), 0),
              end: Alignment(1 - 2 * (1 - t), 0),
              colors: const <Color>[
                AppColors.surfaceTint,
                Color(0xFFFFFFFF),
                AppColors.surfaceTint,
              ],
              stops: const <double>[0.25, 0.5, 0.75],
            ).createShader(bounds);
          },
          child: child,
        );
      },
      child: widget.child,
    );
  }
}

Widget _shimmerBox({
  required double height,
  double? width,
  BorderRadius radius = AppRadii.allMd,
}) {
  return Container(
    height: height,
    width: width,
    decoration: BoxDecoration(
      color: AppColors.surfaceTint,
      borderRadius: radius,
    ),
  );
}

/// Placeholder for the Home patient carousel.
class SkeletonPatientCard extends StatelessWidget {
  const SkeletonPatientCard(
      {super.key, this.width = AppSpacing.patientCardWidth});

  final double width;

  @override
  Widget build(BuildContext context) {
    return _Shimmer(
      radius: AppRadii.allLg,
      child: Container(
        width: width,
        height: AppSpacing.patientCardHeight,
        decoration: const BoxDecoration(
          color: AppColors.surfaceTint,
          borderRadius: AppRadii.allLg,
        ),
      ),
    );
  }
}

/// Placeholder for list rows (`LinkRowCard` shape).
class SkeletonRow extends StatelessWidget {
  const SkeletonRow({super.key, this.thumbnail = 64, this.lines = 2});

  final double thumbnail;
  final int lines;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.cardGap),
      decoration: const BoxDecoration(
          color: AppColors.surface, borderRadius: AppRadii.allLg),
      child: Row(
        children: <Widget>[
          _Shimmer(
            radius: AppRadii.allMd,
            child: _shimmerBox(height: thumbnail, width: thumbnail),
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                for (int i = 0; i < lines; i++)
                  Padding(
                    padding: EdgeInsets.only(
                        bottom: i == lines - 1 ? 0 : AppSpacing.xs),
                    child: _Shimmer(
                      child: _shimmerBox(height: 12, width: i == 0 ? 160 : 110),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Placeholder for a white content card.
class SkeletonCard extends StatelessWidget {
  const SkeletonCard({super.key, this.height = 120, this.padding});

  final double height;
  final EdgeInsets? padding;

  @override
  Widget build(BuildContext context) {
    return _Shimmer(
      child: Container(
        height: height,
        padding: padding ?? const EdgeInsets.all(AppSpacing.cardGap),
        decoration: const BoxDecoration(
            color: AppColors.surface, borderRadius: AppRadii.allLg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: <Widget>[
            _shimmerBox(height: 14, width: 180),
            const SizedBox(height: AppSpacing.sm),
            _shimmerBox(height: 10, width: 240),
            const SizedBox(height: AppSpacing.xs),
            _shimmerBox(height: 10, width: 200),
          ],
        ),
      ),
    );
  }
}

/// Placeholder for the timeline rail + cards.
class SkeletonRail extends StatelessWidget {
  const SkeletonRail({super.key, this.items = 3});

  final int items;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        for (int i = 0; i < items; i++)
          IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Column(
                  children: <Widget>[
                    const SizedBox(height: 4),
                    _Shimmer(
                      radius: BorderRadius.circular(999),
                      child: Container(
                        width: 32,
                        height: 32,
                        decoration: const BoxDecoration(
                          color: AppColors.surfaceTint,
                          shape: BoxShape.circle,
                        ),
                      ),
                    ),
                    Expanded(
                      child: CustomPaint(
                        size: const Size(2, 40),
                        painter: _DotLinePainter(),
                      ),
                    ),
                  ],
                ),
                const SizedBox(width: AppSpacing.sm),
                const Expanded(
                    child: SkeletonCard(
                        height: 96, padding: EdgeInsets.all(AppSpacing.sm))),
              ],
            ),
          ),
      ],
    );
  }
}

class _DotLinePainter extends CustomPainter {
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
      canvas.drawLine(Offset(size.width / 2, y),
          Offset(size.width / 2, (y + dash).clamp(0, size.height)), paint);
      y += dash + gap;
    }
  }

  @override
  bool shouldRepaint(_DotLinePainter oldDelegate) => false;
}

/// Glyph in a soft circle + serif title + body + optional primary pill.
class EmptyState extends StatelessWidget {
  const EmptyState({
    super.key,
    required this.title,
    required this.message,
    this.icon = 'fileText',
    this.actionLabel,
    this.onAction,
    this.compact = false,
  });

  final String title;
  final String message;
  final String icon;
  final String? actionLabel;
  final VoidCallback? onAction;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.symmetric(
        horizontal: AppSpacing.screenH,
        vertical: compact ? AppSpacing.xl : AppSpacing.xxxl,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Container(
            width: 64,
            height: 64,
            decoration: const BoxDecoration(
                color: AppColors.primarySoft, shape: BoxShape.circle),
            alignment: Alignment.center,
            child:
                Icon(AppIcons.byName(icon), size: 26, color: AppColors.primary),
          ),
          SizedBox(height: compact ? AppSpacing.md : AppSpacing.lg),
          Text(
            title,
            style: AppTypography.titleHeader,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            message,
            style: AppTypography.body.copyWith(color: AppColors.textSecondary),
            textAlign: TextAlign.center,
          ),
          if (actionLabel != null && onAction != null) ...<Widget>[
            const SizedBox(height: AppSpacing.lg),
            SizedBox(
              width: 220,
              child: PrimaryPillButton(
                  label: actionLabel!, onPressed: onAction, height: 48),
            ),
          ],
        ],
      ),
    );
  }
}

/// Same layout as [EmptyState] with a typed message and a Retry action.
class ErrorStateView extends StatelessWidget {
  const ErrorStateView({
    super.key,
    required this.message,
    this.title = 'Something went wrong',
    this.onRetry,
    this.retryLabel = 'Retry',
    this.icon = 'alertTriangle',
    this.compact = false,
  });

  final String message;
  final String title;
  final VoidCallback? onRetry;
  final String retryLabel;
  final String icon;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.symmetric(
        horizontal: AppSpacing.screenH,
        vertical: compact ? AppSpacing.xl : AppSpacing.xxxl,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Container(
            width: 64,
            height: 64,
            decoration: const BoxDecoration(
                color: AppColors.warningSoft, shape: BoxShape.circle),
            alignment: Alignment.center,
            child:
                Icon(AppIcons.byName(icon), size: 26, color: AppColors.warning),
          ),
          SizedBox(height: compact ? AppSpacing.md : AppSpacing.lg),
          Text(title,
              style: AppTypography.titleHeader, textAlign: TextAlign.center),
          const SizedBox(height: AppSpacing.xs),
          Text(
            message,
            style: AppTypography.body.copyWith(color: AppColors.textSecondary),
            textAlign: TextAlign.center,
          ),
          if (onRetry != null) ...<Widget>[
            const SizedBox(height: AppSpacing.lg),
            SizedBox(
              width: 200,
              child: PrimaryPillButton(
                label: retryLabel,
                icon: 'refreshCw',
                onPressed: onRetry,
                height: 48,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// Snackbar helpers — plan §11.5.
abstract final class AppSnack {
  const AppSnack._();

  static void show(BuildContext context, String message,
      {bool isError = false}) {
    final ScaffoldMessengerState messenger = ScaffoldMessenger.of(context);
    messenger.hideCurrentSnackBar();
    messenger.showSnackBar(
      SnackBar(
        content: Row(
          children: <Widget>[
            Icon(
              AppIcons.byName(isError ? 'alertTriangle' : 'checkCircle'),
              size: 16,
              color: isError ? AppColors.warning : AppColors.primarySoft,
            ),
            const SizedBox(width: AppSpacing.xs),
            Expanded(
                child: Text(message,
                    style:
                        AppTypography.body.copyWith(color: AppColors.surface))),
          ],
        ),
        duration: const Duration(seconds: 3),
        margin: const EdgeInsets.all(AppSpacing.md),
      ),
    );
  }

  static void error(BuildContext context, String message) =>
      show(context, message, isError: true);
}

/// Banner used for `needs_review`, blocked approval and clinical disclaimers.
class ClinNoticeBanner extends StatelessWidget {
  const ClinNoticeBanner({
    super.key,
    required this.message,
    this.icon = 'info',
    this.tone = ClinNoticeTone.info,
    this.actionLabel,
    this.onAction,
  });

  final String message;
  final String icon;
  final ClinNoticeTone tone;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    final (Color fg, Color bg) = switch (tone) {
      ClinNoticeTone.info => (AppColors.info, AppColors.infoSoft),
      ClinNoticeTone.warning => (AppColors.warning, AppColors.warningSoft),
      ClinNoticeTone.danger => (AppColors.danger, AppColors.dangerSoft),
      ClinNoticeTone.neutral => (
          AppColors.textSecondary,
          AppColors.surfaceTint
        ),
      ClinNoticeTone.primary => (AppColors.primaryDark, AppColors.primarySoft),
    };

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.sm),
      decoration: BoxDecoration(color: bg, borderRadius: AppRadii.allMd),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Icon(AppIcons.byName(icon), size: 16, color: fg),
          const SizedBox(width: AppSpacing.xs),
          Expanded(
            child: Text(
              message,
              style: AppTypography.bodyBullet.copyWith(color: fg, fontSize: 12),
            ),
          ),
          if (actionLabel != null && onAction != null)
            GestureDetector(
              onTap: onAction,
              child: Padding(
                padding: const EdgeInsets.only(left: AppSpacing.xs),
                child: Text(actionLabel!,
                    style: AppTypography.link.copyWith(color: fg)),
              ),
            ),
        ],
      ),
    );
  }
}

enum ClinNoticeTone { info, warning, danger, neutral, primary }

/// The persistent clinical disclaimer — plan §6.6 rule 6.
class ClinicalDisclaimer extends StatelessWidget {
  const ClinicalDisclaimer({super.key, this.text});

  static const String defaultText =
      'AI-assisted summary of source records. Not a diagnosis or treatment recommendation.';

  final String? text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.screenH,
        vertical: AppSpacing.md,
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Icon(AppIcons.byName('info'),
              size: 13, color: AppColors.textTertiary),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              text ?? defaultText,
              style: AppTypography.caption.copyWith(
                color: AppColors.textTertiary,
                fontSize: 10.5,
                height: 1.45,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
