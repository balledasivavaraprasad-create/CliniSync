import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/animations/motion.dart';
import '../../core/constants/enums.dart';
import '../../core/models/document.dart';
import '../../core/repositories/providers.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/utils/confidence_band.dart';
import '../../core/utils/date_format.dart';
import '../../shared/cards/clin_cards.dart';
import '../../shared/loading/states.dart';
import '../../shared/widgets/app_icons.dart';
import '../../shared/widgets/primitives.dart';
import '../state/feature_providers.dart';

/// Document processing — plan §9.5.
///
/// Template: reference screen 3's progress ring + screen 2's timeline rail.
/// `GET /documents/{id}/status` is polled every 1.5 s until terminal; when the
/// endpoint is unavailable the screen falls back to client-side staged progress.
class ProcessingScreen extends ConsumerWidget {
  const ProcessingScreen({
    super.key,
    required this.patientId,
    required this.documentId,
    this.documentName,
  });

  final String patientId;
  final String documentId;
  final String? documentName;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncSlice<ProcessingStatusSnapshot> slice =
        ref.watch(processingProvider(documentId));
    final AsyncSlice<List<ClinicalDocument>> docs =
        ref.watch(documentsProvider(patientId));

    // Prefer the authoritative status endpoint; otherwise use the document row.
    final ProcessingStatusSnapshot? snap = slice.data;
    ClinicalDocument? document;
    for (final ClinicalDocument d in docs.data ?? const <ClinicalDocument>[]) {
      if (d.id == documentId) document = d;
    }
    final ProcessingStatus status =
        snap?.status ?? document?.processingStatus ?? ProcessingStatus.uploaded;
    final double progress = snap?.progress ?? _fallbackProgress(status);
    final String? errorCode = snap?.errorCode ?? document?.processingErrorCode;

    final bool failed = status == ProcessingStatus.failed;
    final bool needsReview = status == ProcessingStatus.needsReview;
    final bool complete = status == ProcessingStatus.complete;

    return Scaffold(
      backgroundColor: AppColors.bgCanvas,
      body: SafeArea(
        bottom: false,
        child: Column(
          children: <Widget>[
            TopBar(
              title: 'Processing',
              subtitle: documentName ?? document?.displayName,
              onLeadingTap: () => context.pop(),
              trailing: <Widget>[
                CircleIconButton(
                  icon: 'refreshCw',
                  tooltip: 'Re-check status',
                  onTap: () =>
                      ref.read(processingProvider(documentId).notifier).retry(),
                ),
              ],
            ),
            Expanded(
              child: ListView(
                padding: EdgeInsets.zero,
                children: <Widget>[
                  // ── Big progress ring
                  SectionReveal(
                    index: 0,
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(
                        AppSpacing.screenH,
                        AppSpacing.md,
                        AppSpacing.screenH,
                        0,
                      ),
                      child: ProgressRingCard(
                        title: failed
                            ? 'Processing failed'
                            : complete
                                ? 'Extraction complete'
                                : 'Working on this record',
                        progress: progress,
                        valueLabel: '${(progress * 100).round()}%',
                        caption: failed
                            ? (errorCode ?? 'DOCUMENT_PROCESSING_FAILED')
                            : complete
                                ? 'All clinical facts are linked to their source text.'
                                : status.label,
                        glyph: failed
                            ? 'alertTriangle'
                            : complete
                                ? 'badgeCheck'
                                : 'sparkles',
                        accent: failed
                            ? AppColors.danger
                            : needsReview
                                ? AppColors.warning
                                : AppColors.primary,
                      ),
                    ),
                  ),

                  if (failed)
                    const SectionReveal(
                      index: 1,
                      child: Padding(
                        padding: EdgeInsets.fromLTRB(
                          AppSpacing.screenH,
                          AppSpacing.sm,
                          AppSpacing.screenH,
                          0,
                        ),
                        child: ClinNoticeBanner(
                          message:
                              'We couldn\'t read this document. Try a clearer scan, or reprocess it.',
                          tone: ClinNoticeTone.danger,
                          icon: 'alertTriangle',
                        ),
                      ),
                    ),

                  if (needsReview)
                    SectionReveal(
                      index: 1,
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(
                          AppSpacing.screenH,
                          AppSpacing.sm,
                          AppSpacing.screenH,
                          0,
                        ),
                        child: ClinNoticeBanner(
                          message:
                              'Some extracted facts need your review before they can be relied on.',
                          tone: ClinNoticeTone.warning,
                          icon: 'alertTriangle',
                          actionLabel: 'Review facts',
                          onAction: () =>
                              context.push('/patients/$patientId/facts'),
                        ),
                      ),
                    ),

                  // ── 6-stage stepper
                  SectionReveal(
                    index: 2,
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(
                        AppSpacing.screenH,
                        AppSpacing.lg,
                        AppSpacing.screenH,
                        0,
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Text('Pipeline', style: AppTypography.titleSection),
                          const SizedBox(height: AppSpacing.sm),
                          _StageStepper(status: status, failed: failed),
                        ],
                      ),
                    ),
                  ),

                  if (document != null)
                    SectionReveal(
                      index: 3,
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(
                          AppSpacing.screenH,
                          AppSpacing.lg,
                          AppSpacing.screenH,
                          0,
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            Text('Source', style: AppTypography.titleSection),
                            const SizedBox(height: AppSpacing.sm),
                            LinkRowCard(
                              title: document.displayName,
                              label: document.documentType.label,
                              meta:
                                  '${AppDate.date(document.documentDate)} • ${document.sizeLabel}',
                              thumbnailIcon: document.documentType.icon,
                            ),
                            const SizedBox(height: AppSpacing.sm),
                            Wrap(
                              spacing: 6,
                              runSpacing: 6,
                              children: <Widget>[
                                if (document.classificationConfidence != null)
                                  ConfidenceBadge(
                                    band: ConfidenceBand.fromValue(
                                        document.classificationConfidence!),
                                    score: document.classificationConfidence,
                                    dense: true,
                                  ),
                                if (document.ocrMethod != null)
                                  StatusPill(
                                    label: 'OCR ${document.ocrMethod}',
                                    variant: StatusPillVariant.neutral,
                                    dense: true,
                                  ),
                                if (document.pageCount > 0)
                                  StatusPill(
                                    label: '${document.pageCount} page'
                                        '${document.pageCount == 1 ? '' : 's'}',
                                    variant: StatusPillVariant.neutral,
                                    dense: true,
                                  ),
                                if (document.isFallback)
                                  const StatusPill(
                                    label: 'Demo data',
                                    variant: StatusPillVariant.demo,
                                    dense: true,
                                  ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ),

                  const SizedBox(height: AppSpacing.md),
                  const ClinicalDisclaimer(),
                  const SizedBox(height: AppSpacing.stickyBarHeight),
                ],
              ),
            ),
          ],
        ),
      ),
      bottomNavigationBar: StickyActionBar(
        primaryLabel: failed
            ? 'Retry processing'
            : complete
                ? 'View Extracted Facts'
                : 'Working…',
        primaryIcon: failed ? 'refreshCw' : (complete ? 'sparkles' : 'loader'),
        enabled: failed || complete,
        onPrimary: failed
            ? () async {
                try {
                  await ref
                      .read(documentRepositoryProvider)
                      .reprocess(documentId);
                  await ref
                      .read(processingProvider(documentId).notifier)
                      .retry();
                  if (context.mounted) {
                    AppSnack.show(context, 'Reprocessing started');
                  }
                } catch (_) {
                  if (context.mounted) {
                    AppSnack.error(context, 'Could not start again.');
                  }
                }
              }
            : () => context.push('/patients/$patientId/facts'),
      ),
    );
  }

  static double _fallbackProgress(ProcessingStatus status) => switch (status) {
        ProcessingStatus.uploaded => 0.08,
        ProcessingStatus.extractingText => 0.25,
        ProcessingStatus.classifying => 0.42,
        ProcessingStatus.extractingEntities => 0.62,
        ProcessingStatus.normalizing => 0.8,
        ProcessingStatus.validating => 0.9,
        ProcessingStatus.complete => 1,
        ProcessingStatus.needsReview => 1,
        ProcessingStatus.failed => 1,
      };
}

/// `Uploaded → Extracting text → Classifying → Extracting clinical information
/// → Normalising & linking evidence → Complete`.
class _StageStepper extends StatelessWidget {
  const _StageStepper({required this.status, required this.failed});

  final ProcessingStatus status;
  final bool failed;

  static const List<PipelineStage> _stages = PipelineStage.values;

  /// Index of the stage currently running.
  int get _activeIndex {
    if (failed) return _stages.length - 1;
    switch (status) {
      case ProcessingStatus.uploaded:
        return 0;
      case ProcessingStatus.extractingText:
        return 1;
      case ProcessingStatus.classifying:
        return 2;
      case ProcessingStatus.extractingEntities:
        return 3;
      case ProcessingStatus.normalizing:
      case ProcessingStatus.validating:
        return 4;
      case ProcessingStatus.complete:
      case ProcessingStatus.needsReview:
      case ProcessingStatus.failed:
        return _stages.length;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: <Widget>[
        for (int i = 0; i < _stages.length; i++)
          IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                _StageNode(
                  state: i < _activeIndex
                      ? _NodeState.done
                      : (i == _activeIndex
                          ? _NodeState.active
                          : _NodeState.pending),
                  failed: failed && i == _activeIndex,
                ),
                Expanded(
                  child: Padding(
                    padding: EdgeInsets.only(
                        bottom: i == _stages.length - 1 ? 0 : AppSpacing.md),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          _stages[i].label,
                          style: AppTypography.bodyStrong.copyWith(
                            fontSize: 13.5,
                            color: i <= _activeIndex
                                ? AppColors.textPrimary
                                : AppColors.textTertiary,
                          ),
                        ),
                        if (i == _activeIndex)
                          Padding(
                            padding: const EdgeInsets.only(top: 2),
                            child: Text(
                              failed
                                  ? 'Stopped — try again'
                                  : _captionFor(status),
                              style: AppTypography.bodyBullet
                                  .copyWith(fontSize: 11.5),
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }

  static String _captionFor(ProcessingStatus status) => switch (status) {
        ProcessingStatus.uploaded => 'Queued',
        ProcessingStatus.extractingText => 'Reading text from the document…',
        ProcessingStatus.classifying =>
          'Working out what kind of record this is…',
        ProcessingStatus.extractingEntities =>
          'Pulling out diagnoses, medications, results…',
        ProcessingStatus.normalizing =>
          'Linking every claim to its source span…',
        ProcessingStatus.validating => 'Checking provenance and confidence…',
        _ => 'Done',
      };
}

enum _NodeState { done, active, pending }

class _StageNode extends StatelessWidget {
  const _StageNode({required this.state, required this.failed});

  final _NodeState state;
  final bool failed;

  @override
  Widget build(BuildContext context) {
    final (Color bg, Color fg, IconData? glyph) = switch (state) {
      _NodeState.done => (
          AppColors.primary,
          AppColors.onPrimary,
          AppIcons.byName('check')
        ),
      _NodeState.active => (
          failed ? AppColors.danger : AppColors.primary,
          AppColors.onPrimary,
          null,
        ),
      _NodeState.pending => (
          AppColors.surfaceTint,
          AppColors.textTertiary,
          null
        ),
    };

    return SizedBox(
      width: 34,
      child: Column(
        children: <Widget>[
          SoftPulse(
            active: state == _NodeState.active,
            child: Container(
              width: 26,
              height: 26,
              decoration: BoxDecoration(color: bg, shape: BoxShape.circle),
              alignment: Alignment.center,
              child: glyph == null
                  ? (state == _NodeState.active
                      ? Container(
                          width: 8,
                          height: 8,
                          decoration:
                              BoxDecoration(color: fg, shape: BoxShape.circle),
                        )
                      : null)
                  : Icon(glyph, size: 14, color: fg),
            ),
          ),
          Expanded(
            child: CustomPaint(
              size: const Size(2, 20),
              painter:
                  _StepperConnectorPainter(active: state == _NodeState.done),
            ),
          ),
        ],
      ),
    );
  }
}

class _StepperConnectorPainter extends CustomPainter {
  const _StepperConnectorPainter({required this.active});

  final bool active;

  @override
  void paint(Canvas canvas, Size size) {
    final Paint paint = Paint()
      ..color = active ? AppColors.primarySoft : AppColors.divider
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
  bool shouldRepaint(_StepperConnectorPainter oldDelegate) =>
      oldDelegate.active != active;
}
