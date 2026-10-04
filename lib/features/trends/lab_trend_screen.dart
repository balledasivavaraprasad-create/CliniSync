import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/animations/motion.dart';
import '../../core/constants/enums.dart';
import '../../core/models/investigation.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/utils/date_format.dart';
import '../../shared/cards/clin_cards.dart';
import '../../shared/loading/states.dart';
import '../../shared/widgets/app_icons.dart';
import '../../shared/widgets/primitives.dart';
import '../state/feature_providers.dart';

/// Lab trend — plan §9.11.
///
/// A large `MetricCard`, an `fl_chart` line card styled with `primary`, and the
/// measurement history. The sentence is the backend's own non-causal
/// description — the client never invents one.
class LabTrendScreen extends ConsumerWidget {
  const LabTrendScreen({
    super.key,
    required this.patientId,
    required this.groupKey,
    this.testName,
  });

  final String patientId;
  final String groupKey;
  final String? testName;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ({String patientId, String groupKey}) args =
        (patientId: patientId, groupKey: groupKey);
    final AsyncValue<InvestigationTrend> async =
        ref.watch(investigationTrendProvider(args));
    final AsyncSlice<List<Investigation>> latest =
        ref.watch(investigationsProvider(patientId));

    // Reference range from the latest measurement, when available.
    Investigation? current;
    for (final Investigation i in latest.data ?? const <Investigation>[]) {
      if (i.groupKey == groupKey || i.testName == groupKey) current = i;
    }

    return Scaffold(
      backgroundColor: AppColors.bgCanvas,
      body: SafeArea(
        bottom: false,
        child: Column(
          children: <Widget>[
            TopBar(
              title: testName ?? groupKey,
              subtitle: 'Lab trend',
              onLeadingTap: () => context.pop(),
              trailing: <Widget>[
                CircleIconButton(
                  icon: 'refreshCw',
                  tooltip: 'Reload',
                  onTap: () => ref.invalidate(investigationTrendProvider(args)),
                ),
              ],
            ),
            Expanded(
              child: async.when(
                loading: () => const Padding(
                  padding: EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
                  child: Column(
                    children: <Widget>[
                      SkeletonCard(height: 160),
                      SizedBox(height: AppSpacing.lg),
                      SkeletonCard(height: 220),
                    ],
                  ),
                ),
                error: (Object e, StackTrace _) => ErrorStateView(
                  message: 'We couldn\'t load this trend.',
                  onRetry: () =>
                      ref.invalidate(investigationTrendProvider(args)),
                ),
                data: (InvestigationTrend trend) => _TrendBody(
                  trend: trend,
                  current: current,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _TrendBody extends StatelessWidget {
  const _TrendBody({required this.trend, this.current});

  final InvestigationTrend trend;
  final Investigation? current;

  @override
  Widget build(BuildContext context) {
    final List<TrendPoint> points = trend.numericPoints;

    if (points.isEmpty) {
      return EmptyState(
        icon: 'flaskConical',
        title: 'No measurements recorded',
        message: 'No values were extracted for ${trend.displayName}.',
      );
    }

    return ListView(
      padding: EdgeInsets.zero,
      children: <Widget>[
        // ── Latest value + delta
        SectionReveal(
          index: 0,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.screenH,
              AppSpacing.md,
              AppSpacing.screenH,
              0,
            ),
            child: MetricCard(
              title: trend.displayName,
              value: _latestLabel(trend, points),
              unit: trend.unit ?? '',
              caption1: trend.deltaLabel,
              caption2: current?.referenceLine,
              iconName: 'flaskConical',
              statusPill: current == null
                  ? null
                  : current!.abnormalFlag.isAbnormal
                      ? StatusPill(
                          label: current!.abnormalFlag.label,
                          variant: StatusPillVariant.needsReview,
                          dense: true,
                        )
                      : const StatusPill(
                          label: 'In range',
                          variant: StatusPillVariant.approved,
                          dense: true,
                        ),
            ),
          ),
        ),

        const SizedBox(height: AppSpacing.md),

        // ── Chart
        SectionReveal(
          index: 1,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
            child: points.length < 2
                ? const ClinNoticeBanner(
                    message:
                        'Only one measurement — a trend needs at least two.',
                    icon: 'info',
                    tone: ClinNoticeTone.neutral,
                  )
                : _TrendChart(points: points, current: current),
          ),
        ),

        const SizedBox(height: AppSpacing.lg),

        // ── The backend's non-causal sentence
        SectionReveal(
          index: 2,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
            child: SurfaceCard(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text('What the records show',
                      style: AppTypography.titleSection),
                  const SizedBox(height: AppSpacing.xs),
                  Text(trend.descriptionText, style: AppTypography.body),
                  const SizedBox(height: AppSpacing.xs),
                  Row(
                    children: <Widget>[
                      Icon(
                        AppIcons.byName(trend.direction == TrendDirection.up
                            ? 'trendingUp'
                            : trend.direction == TrendDirection.down
                                ? 'trendingDown'
                                : 'equal'),
                        size: 14,
                        color: AppColors.primary,
                      ),
                      const SizedBox(width: 5),
                      Text(trend.direction.label,
                          style: AppTypography.capsLabel.copyWith(
                            color: AppColors.textSecondary,
                            fontSize: 10,
                          )),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),

        const SizedBox(height: AppSpacing.lg),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
          child: Text('History', style: AppTypography.titleSection),
        ),
        const SizedBox(height: AppSpacing.sm),

        // ── Measurement rows
        SectionReveal(
          index: 3,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
            child: Column(
              children: <Widget>[
                for (int i = points.length - 1; i >= 0; i--)
                  Padding(
                    padding: const EdgeInsets.only(bottom: AppSpacing.xs),
                    child: LinkRowCard(
                      title: _fmt(points[i].value) +
                          ((points[i].unit ?? trend.unit ?? '').isEmpty
                              ? ''
                              : ' ${points[i].unit ?? trend.unit}'),
                      label: points[i].dateLabel ?? AppDate.undatedLabel,
                      meta: points[i].abnormalFlag.isAbnormal
                          ? points[i].abnormalFlag.label
                          : AppDate.date(points[i].isoDate),
                      thumbnailIcon: 'flaskConical',
                    ),
                  ),
              ],
            ),
          ),
        ),

        const SizedBox(height: AppSpacing.md),
        const ClinicalDisclaimer(),
        const SizedBox(height: AppSpacing.xxl),
      ],
    );
  }

  static String _latestLabel(
          InvestigationTrend trend, List<TrendPoint> points) =>
      _fmt(points.last.value);

  static String _fmt(double v) =>
      v == v.roundToDouble() ? v.toStringAsFixed(0) : v.toStringAsFixed(1);
}

/// Line chart: `primary` stroke, soft gradient fill, rounded stroke,
/// reference-range band when available. The line draws left → right over 700 ms.
class _TrendChart extends StatelessWidget {
  const _TrendChart({required this.points, this.current});

  final List<TrendPoint> points;
  final Investigation? current;

  @override
  Widget build(BuildContext context) {
    final double? low = current?.referenceLow;
    final double? high = current?.referenceHigh;
    final double min = (trendMin(points, low) - 0.4).floorToDouble();
    final double max = (trendMax(points, high) + 0.4).ceilToDouble();

    final LineChartBarData line = LineChartBarData(
      spots: <FlSpot>[
        for (int i = 0; i < points.length; i++)
          FlSpot(i.toDouble(), points[i].value),
      ],
      isCurved: true,
      curveSmoothness: 0.22,
      preventCurveOverShooting: true,
      barWidth: 2.6,
      color: AppColors.primary,
      dotData: FlDotData(
        show: true,
        getDotPainter:
            (FlSpot spot, double percent, LineChartBarData bar, int index) =>
                FlDotCirclePainter(
          radius: 4,
          color: AppColors.surface,
          strokeWidth: 2.4,
          strokeColor: AppColors.primary,
        ),
      ),
      belowBarData: BarAreaData(
        show: true,
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: <Color>[
            AppColors.primary.withValues(alpha: 0.22),
            AppColors.primary.withValues(alpha: 0.02),
          ],
        ),
      ),
    );

    return SurfaceCard(
      padding: const EdgeInsets.fromLTRB(
          AppSpacing.sm, AppSpacing.md, AppSpacing.md, AppSpacing.sm),
      child: SizedBox(
        height: 200,
        child: LineChart(
          LineChartData(
            minY: min == max ? min - 1 : min,
            maxY: max == min ? max + 1 : max,
            minX: 0,
            maxX: (points.length - 1).toDouble() < 1
                ? 1
                : (points.length - 1).toDouble(),
            // The reference range is drawn as a true band between the low and
            // high limits, so "in range" is visually unambiguous.
            rangeAnnotations: RangeAnnotations(
              horizontalRangeAnnotations: <HorizontalRangeAnnotation>[
                if (low != null && high != null && high > low)
                  HorizontalRangeAnnotation(
                    y1: low,
                    y2: high,
                    color: AppColors.primaryWash.withValues(alpha: 0.9),
                  ),
              ],
            ),
            gridData: FlGridData(
              show: true,
              drawVerticalLine: false,
              horizontalInterval: _interval(min, max),
              getDrawingHorizontalLine: (double value) => const FlLine(
                color: AppColors.divider,
                strokeWidth: 1,
                dashArray: <int>[3, 4],
              ),
            ),
            borderData: FlBorderData(show: false),
            titlesData: FlTitlesData(
              topTitles:
                  const AxisTitles(sideTitles: SideTitles(showTitles: false)),
              rightTitles:
                  const AxisTitles(sideTitles: SideTitles(showTitles: false)),
              leftTitles: AxisTitles(
                sideTitles: SideTitles(
                  showTitles: true,
                  reservedSize: 38,
                  interval: _interval(min, max),
                  getTitlesWidget: (double value, TitleMeta meta) => Padding(
                    padding: const EdgeInsets.only(right: 4),
                    child: Text(
                      _short(value),
                      style: AppTypography.caption.copyWith(fontSize: 9.5),
                    ),
                  ),
                ),
              ),
              bottomTitles: AxisTitles(
                sideTitles: SideTitles(
                  showTitles: true,
                  reservedSize: 26,
                  interval: 1,
                  getTitlesWidget: (double value, TitleMeta meta) {
                    final int i = value.round();
                    if (i < 0 || i >= points.length) {
                      return const SizedBox.shrink();
                    }
                    return Padding(
                      padding: const EdgeInsets.only(top: 6),
                      child: Text(
                        points[i].shortLabel,
                        style: AppTypography.caption.copyWith(fontSize: 9.5),
                      ),
                    );
                  },
                ),
              ),
            ),
            lineBarsData: <LineChartBarData>[line],
          ),
          duration: const Duration(milliseconds: 700),
          curve: Curves.easeOutCubic,
        ),
      ),
    );
  }

  static double trendMin(List<TrendPoint> points, double? refLow) {
    double m = points.first.value;
    for (final TrendPoint p in points) {
      if (p.value < m) m = p.value;
    }
    if (refLow != null && refLow < m) m = refLow;
    return m;
  }

  static double trendMax(List<TrendPoint> points, double? refHigh) {
    double m = points.first.value;
    for (final TrendPoint p in points) {
      if (p.value > m) m = p.value;
    }
    if (refHigh != null && refHigh > m) m = refHigh;
    return m;
  }

  static double _interval(double min, double max) {
    final double span = (max - min).abs();
    if (span <= 2) return 1;
    if (span <= 10) return 2;
    return (span / 4).ceilToDouble();
  }

  static String _short(double v) =>
      v == v.roundToDouble() ? v.toStringAsFixed(0) : v.toStringAsFixed(1);
}

/// Sparkline used inside the Brief's `Important Trends` section (plan §9.14).
class TrendSparkline extends StatelessWidget {
  const TrendSparkline({super.key, required this.values, this.height = 26});

  final List<double> values;
  final double height;

  @override
  Widget build(BuildContext context) {
    if (values.length < 2) {
      return SizedBox(
        height: height,
        child: Center(
          child: Text('Not enough data', style: AppTypography.caption),
        ),
      );
    }
    final double lo = values.reduce((double a, double b) => a < b ? a : b);
    final double hi = values.reduce((double a, double b) => a > b ? a : b);
    final double span = (hi - lo).abs() < 0.0001 ? 1 : hi - lo;

    return SizedBox(
      height: height,
      width: 84,
      child: CustomPaint(
          painter: _SparkPainter(values: values, lo: lo, span: span)),
    );
  }
}

class _SparkPainter extends CustomPainter {
  const _SparkPainter(
      {required this.values, required this.lo, required this.span});

  final List<double> values;
  final double lo;
  final double span;

  @override
  void paint(Canvas canvas, Size size) {
    final Paint stroke = Paint()
      ..color = AppColors.primary
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;

    final Path path = Path();
    for (int i = 0; i < values.length; i++) {
      final double x =
          values.length == 1 ? 0 : size.width * i / (values.length - 1);
      final double norm = (values[i] - lo) / span;
      final double y = size.height - (norm * (size.height - 4)) - 2;
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    canvas.drawPath(path, stroke);

    final Paint dot = Paint()..color = AppColors.primary;
    final double lastX = size.width;
    final double lastNorm = (values.last - lo) / span;
    canvas.drawCircle(
        Offset(lastX, size.height - (lastNorm * (size.height - 4)) - 2),
        2.6,
        dot);
  }

  @override
  bool shouldRepaint(_SparkPainter oldDelegate) => oldDelegate.values != values;
}
