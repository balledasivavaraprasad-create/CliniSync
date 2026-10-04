import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/animations/motion.dart';
import '../../core/constants/app_assets.dart';
import '../../core/constants/enums.dart';
import '../../core/models/clinical_fact.dart';
import '../../core/models/clinical_memory.dart';
import '../../core/models/document.dart';
import '../../core/models/investigation.dart';
import '../../core/models/medication.dart';
import '../../core/models/patient.dart';
import '../../core/models/timeline_event.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_radii.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/utils/date_format.dart';
import '../../shared/cards/clin_cards.dart';
import '../../shared/loading/states.dart';
import '../../shared/widgets/app_icons.dart';
import '../../shared/widgets/primitives.dart';
import '../state/feature_providers.dart';

/// The 4 overview tabs — plan §9.3 `PillTabs`.
enum OverviewTab { timeline, medications, investigations, issues }

const List<String> kOverviewTabLabels = <String>[
  'Timeline',
  'Medications',
  'Investigations',
  'Issues',
];

/// Shared tab-body widget so Overview and the full screens render identically.
class OverviewTabBody extends ConsumerStatefulWidget {
  const OverviewTabBody({
    super.key,
    required this.patientId,
    required this.tab,
    this.compact = false,
  });

  final String patientId;
  final OverviewTab tab;
  final bool compact;

  @override
  ConsumerState<OverviewTabBody> createState() => _OverviewTabBodyState();
}

class _OverviewTabBodyState extends ConsumerState<OverviewTabBody> {
  @override
  Widget build(BuildContext context) {
    switch (widget.tab) {
      case OverviewTab.timeline:
        return _TimelineTab(
            patientId: widget.patientId, compact: widget.compact);
      case OverviewTab.medications:
        return _MedicationsTab(
            patientId: widget.patientId, compact: widget.compact);
      case OverviewTab.investigations:
        return _InvestigationsTab(
            patientId: widget.patientId, compact: widget.compact);
      case OverviewTab.issues:
        return _IssuesTab(patientId: widget.patientId, compact: widget.compact);
    }
  }
}

// ── Timeline tab ──────────────────────────────────────────────────────────

class _TimelineTab extends ConsumerWidget {
  const _TimelineTab({required this.patientId, required this.compact});

  final String patientId;
  final bool compact;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncSlice<List<TimelineEvent>> slice =
        ref.watch(timelineProvider(patientId));
    if (slice.loading && !slice.hasData) return const SkeletonRail();
    if (slice.hasError && !slice.hasData) {
      return ErrorStateView(
        message: slice.error!.message,
        onRetry: () => ref.read(timelineProvider(patientId).notifier).refresh(),
        compact: true,
      );
    }
    final List<TimelineEvent> events = slice.data ?? const <TimelineEvent>[];
    if (events.isEmpty) {
      return const EmptyState(
        icon: 'history',
        title: 'No events yet',
        message: 'Upload a record and the timeline will be built from it.',
        compact: true,
      );
    }

    final int limit = compact ? 5 : events.length;
    return Column(
      children: <Widget>[
        for (int i = 0; i < limit && i < events.length; i++)
          SectionReveal(
            index: i,
            child: Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.sm),
              child: DatedTimelineEntry(
                date: events[i].eventDate,
                isFirst: i == 0,
                isLast: i == limit - 1,
                child: TimelineCard(
                  iconName: events[i].eventType.icon,
                  title: events[i].title,
                  bullet1: events[i].summary,
                  bullet2: events[i].relatedFactIds.isEmpty
                      ? null
                      : '${events[i].relatedFactIds.length} evidence-backed fact'
                          '${events[i].relatedFactIds.length == 1 ? '' : 's'}',
                  onTap: () {
                    final String? factId = events[i].relatedFactIds.isEmpty
                        ? null
                        : events[i].relatedFactIds.first;
                    if (factId != null) context.push('/facts/$factId/evidence');
                  },
                  onChevronTap: events[i].relatedFactIds.isEmpty
                      ? null
                      : () => context.push(
                          '/facts/${events[i].relatedFactIds.first}/evidence'),
                  thumbnailIcon: events[i].sourceDocumentId == null
                      ? events[i].eventType.icon
                      : 'fileText',
                ),
              ),
            ),
          ),
      ],
    );
  }
}

// ── Medications tab ───────────────────────────────────────────────────────

class _MedicationsTab extends ConsumerWidget {
  const _MedicationsTab({required this.patientId, required this.compact});

  final String patientId;
  final bool compact;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncSlice<List<Medication>> slice =
        ref.watch(medicationsProvider(patientId));
    if (slice.loading && !slice.hasData) {
      return const Column(
        children: <Widget>[
          SkeletonCard(height: 84),
          SizedBox(height: AppSpacing.xs),
          SkeletonCard(height: 84),
        ],
      );
    }
    if (slice.hasError && !slice.hasData) {
      return ErrorStateView(
        message: slice.error!.message,
        onRetry: () =>
            ref.read(medicationsProvider(patientId).notifier).refresh(),
        compact: true,
      );
    }
    final List<Medication> meds = slice.data ?? const <Medication>[];
    if (meds.isEmpty) {
      return const EmptyState(
        icon: 'pill',
        title: 'No medications extracted',
        message:
            'Medication instructions appear here once a prescription is processed.',
        compact: true,
      );
    }

    final List<Medication> shown =
        compact ? meds.take(4).toList(growable: false) : meds;
    return Column(
      children: <Widget>[
        for (int i = 0; i < shown.length; i++)
          SectionReveal(
            index: i,
            child: Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.xs),
              child: MedicationCard(
                medication: shown[i],
                onTap: () => context.push(
                  '/patients/$patientId/medications/${Uri.encodeComponent(shown[i].historyPathSegment)}'
                  '/reconcile?name=${Uri.encodeQueryComponent(shown[i].displayName)}',
                ),
              ),
            ),
          ),
      ],
    );
  }
}

/// Medication row with conflict / change tags. Discrepancies are surfaced,
/// never resolved (plan §9.8).
class MedicationCard extends StatelessWidget {
  const MedicationCard({super.key, required this.medication, this.onTap});

  final Medication medication;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final List<Widget> tags = <Widget>[];
    if (medication.hasConflict) {
      tags.add(const StatusPill(
        label: 'Potential conflict',
        variant: StatusPillVariant.conflict,
        icon: 'alertTriangle',
        dense: true,
      ));
    }
    if (medication.status == MedicationStatus.uncertain) {
      tags.add(const StatusPill(
        label: 'Uncertain status',
        variant: StatusPillVariant.needsReview,
        icon: 'helpCircle',
        dense: true,
      ));
    }
    if (medication.historyCount > 1) {
      tags.add(StatusPill(
        label: 'Changed · ${medication.historyCount} records',
        variant: StatusPillVariant.neutral,
        icon: 'replace',
        dense: true,
      ));
    }

    return SurfaceCard(
      onTap: onTap,
      radius: 20,
      padding: const EdgeInsets.all(AppSpacing.cardGap),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Container(
                width: 34,
                height: 34,
                decoration: const BoxDecoration(
                  color: AppColors.primarySoft,
                  shape: BoxShape.circle,
                ),
                alignment: Alignment.center,
                child: Icon(AppIcons.byName('pill'),
                    size: 16, color: AppColors.primaryDark),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    Text(
                      medication.displayName,
                      style: AppTypography.titleCard.copyWith(fontSize: 14.5),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    Text(
                      medication.doseLine,
                      style: AppTypography.bodyBullet,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
              if (onTap != null)
                Icon(AppIcons.byName('chevronRight'),
                    size: 18, color: AppColors.textTertiary),
            ],
          ),
          if (medication.statusReason != null) ...<Widget>[
            const SizedBox(height: 6),
            Text(
              medication.statusReason!,
              style: AppTypography.caption.copyWith(fontSize: 11),
            ),
          ],
          const SizedBox(height: AppSpacing.xs),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: <Widget>[
              ConfidenceBadge(
                  band: medication.confidenceBand,
                  score: medication.confidence,
                  dense: true),
              ...tags,
            ],
          ),
        ],
      ),
    );
  }
}

// ── Investigations tab ─────────────────────────────────────────────────────

class _InvestigationsTab extends ConsumerWidget {
  const _InvestigationsTab({required this.patientId, required this.compact});

  final String patientId;
  final bool compact;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncSlice<List<Investigation>> slice =
        ref.watch(investigationsProvider(patientId));
    if (slice.loading && !slice.hasData) {
      return const Row(
        children: <Widget>[
          Expanded(child: SkeletonCard(height: 130)),
          SizedBox(width: AppSpacing.xs),
          Expanded(child: SkeletonCard(height: 130)),
        ],
      );
    }
    if (slice.hasError && !slice.hasData) {
      return ErrorStateView(
        message: slice.error!.message,
        onRetry: () =>
            ref.read(investigationsProvider(patientId).notifier).refresh(),
        compact: true,
      );
    }
    final List<Investigation> inv = slice.data ?? const <Investigation>[];
    if (inv.isEmpty) {
      return const EmptyState(
        icon: 'flaskConical',
        title: 'No investigations recorded',
        message: 'Lab results appear here with their reference ranges.',
        compact: true,
      );
    }
    return InvestigationGrid(
      patientId: patientId,
      investigations: inv,
      maxItems: compact ? 4 : inv.length,
    );
  }
}

/// Two-up grid of `MetricCard`s — plan §9.10.
class InvestigationGrid extends StatelessWidget {
  const InvestigationGrid({
    super.key,
    required this.patientId,
    required this.investigations,
    this.maxItems,
  });

  final String patientId;
  final List<Investigation> investigations;
  final int? maxItems;

  @override
  Widget build(BuildContext context) {
    final List<Investigation> shown = maxItems == null
        ? investigations
        : investigations.take(maxItems!).toList(growable: false);
    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints constraints) {
        final int columns = constraints.maxWidth > 420 ? 3 : 2;
        const double gap = AppSpacing.xs;
        final double width =
            (constraints.maxWidth - gap * (columns - 1)) / columns;
        return Wrap(
          spacing: gap,
          runSpacing: gap,
          children: <Widget>[
            for (int i = 0; i < shown.length; i++)
              SizedBox(
                width: width,
                child: SectionReveal(
                  index: i,
                  child: InvestigationMetricCard(
                    investigation: shown[i],
                    onTap: () => context.push(
                      '/patients/$patientId/investigations/'
                      '${Uri.encodeComponent(shown[i].groupKey)}/trend'
                      '?name=${Uri.encodeQueryComponent(shown[i].displayName)}',
                    ),
                  ),
                ),
              ),
          ],
        );
      },
    );
  }
}

class InvestigationMetricCard extends StatelessWidget {
  const InvestigationMetricCard(
      {super.key, required this.investigation, this.onTap});

  final Investigation investigation;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final AbnormalFlag flag = investigation.abnormalFlag;
    return MetricCard(
      title: investigation.displayName,
      value: investigation.displayValue,
      unit: investigation.displayUnit,
      caption1: flag.isAbnormal ? flag.label : investigation.observedLabel,
      caption2: investigation.referenceLine,
      iconName: 'flaskConical',
      accent: flag.isAbnormal ? AppColors.warning : AppColors.primarySoft,
      statusPill: flag.isAbnormal
          ? StatusPill(
              label: flag.label,
              variant: StatusPillVariant.needsReview,
              dense: true,
            )
          : null,
      onTap: onTap,
    );
  }
}

// ── Issues tab ────────────────────────────────────────────────────────────

class _IssuesTab extends ConsumerWidget {
  const _IssuesTab({required this.patientId, required this.compact});

  final String patientId;
  final bool compact;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncSlice<List<ClinicalIssue>> slice =
        ref.watch(issuesProvider(patientId));
    if (slice.loading && !slice.hasData) return const SkeletonCard(height: 120);
    if (slice.hasError && !slice.hasData) {
      return ErrorStateView(
        message: slice.error!.message,
        onRetry: () => ref.read(issuesProvider(patientId).notifier).refresh(),
        compact: true,
      );
    }
    final IssuesNotifier notifier =
        ref.read(issuesProvider(patientId).notifier);
    final List<ClinicalIssue> open = notifier.open;
    if (open.isEmpty) {
      return const EmptyState(
        icon: 'shieldCheck',
        title: 'Nothing needs review',
        message:
            'No open conflicts or missing information were detected in the records processed so far.',
        compact: true,
      );
    }

    final List<ClinicalIssue> shown =
        compact ? open.take(3).toList(growable: false) : open;
    return Column(
      children: <Widget>[
        if (compact)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.xs),
            child: ReviewProgressStrip(
              reviewed: notifier.reviewedCount,
              total: slice.data?.length ?? open.length,
              onTap: () => context.push('/patients/$patientId/issues'),
            ),
          ),
        for (int i = 0; i < shown.length; i++)
          SectionReveal(
            index: i,
            child: Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.xs),
              child: IssueCard(issue: shown[i], compact: true),
            ),
          ),
        if (compact && open.length > shown.length)
          Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Text(
              '+${open.length - shown.length} more',
              style: AppTypography.link,
            ),
          ),
      ],
    );
  }
}

/// `Review progress` ring card — plan §9.12.
class ReviewProgressStrip extends StatelessWidget {
  const ReviewProgressStrip({
    super.key,
    required this.reviewed,
    required this.total,
    this.onTap,
  });

  final int reviewed;
  final int total;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final double progress = total == 0 ? 1 : reviewed / total;
    return ProgressRingCard(
      title: 'Review progress',
      progress: progress,
      valueLabel: '${(progress * 100).round()}%',
      caption: '$reviewed of $total reviewed',
      glyph: 'listChecks',
      onTap: onTap,
    );
  }
}

/// Issue card with severity pill, description, source rows and actions.
class IssueCard extends ConsumerStatefulWidget {
  const IssueCard({
    super.key,
    required this.issue,
    this.patientId,
    this.compact = false,
    this.showActions = true,
  });

  final ClinicalIssue issue;
  final String? patientId;
  final bool compact;
  final bool showActions;

  @override
  ConsumerState<IssueCard> createState() => _IssueCardState();
}

class _IssueCardState extends ConsumerState<IssueCard> {
  bool _busy = false;

  Future<void> _patch(IssueStatus status) async {
    final String? patientId = widget.patientId;
    if (patientId == null) return;
    setState(() => _busy = true);
    try {
      await ref
          .read(issuesProvider(patientId).notifier)
          .patch(widget.issue, status);
      if (mounted) {
        AppSnack.show(
            context, '${widget.issue.title} · ${status.label.toLowerCase()}');
      }
    } catch (_) {
      if (mounted) AppSnack.error(context, 'Could not update that item.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final ClinicalIssue issue = widget.issue;
    final List<String> sources = issue.sourceLines;

    return SurfaceCard(
      radius: 20,
      padding: const EdgeInsets.all(AppSpacing.cardGap),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              StatusPill(
                label: issue.severity.label,
                variant: switch (issue.severity) {
                  Severity.high => StatusPillVariant.conflict,
                  Severity.medium => StatusPillVariant.needsReview,
                  Severity.low => StatusPillVariant.neutral,
                },
                dense: true,
              ),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  issue.title,
                  style: AppTypography.titleCard.copyWith(fontSize: 14),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              if (issue.status != IssueStatus.open)
                const StatusPill(
                    label: 'Reviewed',
                    variant: StatusPillVariant.approved,
                    dense: true),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            issue.isMissingInfo ? issue.prompt : (issue.description ?? ''),
            style: AppTypography.bodyBullet.copyWith(fontSize: 12),
          ),
          if (issue.isMissingInfo && issue.reason.isNotEmpty) ...<Widget>[
            const SizedBox(height: 3),
            Text(issue.reason, style: AppTypography.caption),
          ],
          if (sources.length >= 2) ...<Widget>[
            const SizedBox(height: AppSpacing.xs),
            // Both sources shown side by side; neither is marked correct
            // (plan §6.6 rule 3).
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Expanded(
                    child: _SourceBox(label: 'Source A', text: sources[0])),
                const SizedBox(width: AppSpacing.xs),
                Expanded(
                    child: _SourceBox(label: 'Source B', text: sources[1])),
              ],
            ),
          ],
          if (widget.showActions &&
              issue.isOpen &&
              widget.patientId != null) ...<Widget>[
            const SizedBox(height: AppSpacing.sm),
            Row(
              children: <Widget>[
                Expanded(
                  child: SizedBox(
                    height: 40,
                    child: PressScale(
                      onTap:
                          _busy ? null : () => _patch(IssueStatus.acknowledged),
                      child: Container(
                        decoration: const BoxDecoration(
                          color: AppColors.primarySoft,
                          borderRadius: AppRadii.allPill,
                        ),
                        alignment: Alignment.center,
                        child: Text(
                          'Acknowledge',
                          style: AppTypography.bodyBullet.copyWith(
                            color: AppColors.primaryDark,
                            fontWeight: FontWeight.w600,
                            fontSize: 12.5,
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: AppSpacing.xs),
                Expanded(
                  child: SizedBox(
                    height: 40,
                    child: PressScale(
                      onTap: _busy ? null : () => _patch(IssueStatus.dismissed),
                      child: Container(
                        decoration: const BoxDecoration(
                          color: AppColors.surfaceTint,
                          borderRadius: AppRadii.allPill,
                        ),
                        alignment: Alignment.center,
                        child: Text(
                          'Dismiss',
                          style: AppTypography.bodyBullet.copyWith(
                            fontWeight: FontWeight.w600,
                            fontSize: 12.5,
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _SourceBox extends StatelessWidget {
  const _SourceBox({required this.label, required this.text});

  final String label;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.xs),
      decoration: BoxDecoration(
        color: AppColors.surfaceTint,
        borderRadius: BorderRadius.circular(AppSpacing.xs),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            label.toUpperCase(),
            style: AppTypography.capsLabel
                .copyWith(fontSize: 9, letterSpacing: 0.4),
          ),
          const SizedBox(height: 2),
          Text(text,
              style: AppTypography.bodyBullet.copyWith(fontSize: 10.5),
              maxLines: 5),
        ],
      ),
    );
  }
}

// ── Documents preview used by the header block ────────────────────────────

/// Document-type glyph icons for the `AvatarStack` (plan §6.3).
List<String> documentGlyphs(List<ClinicalDocument> documents) => documents
    .map((ClinicalDocument d) => d.documentType.icon)
    .toList(growable: false);

/// Ambient still chosen per document index.
String documentAmbient(int index) =>
    kPatientAmbientImages[index % kPatientAmbientImages.length];

/// Convenience meta line for the header block — plan §6.4:
/// `54 yrs • Diabetology • Last seen 20 Sep`.
String overviewMetaLine(PatientOverviewParts parts) {
  final List<String> out = <String>[
    AppDate.ageLabel(ageYears: parts.ageYears, dateOfBirth: parts.dateOfBirth),
    parts.specialtyLabel,
    AppDate.relative(parts.lastActivityAt),
  ];
  return out.join(' • ');
}

/// The subset of a patient the meta line needs.
class PatientOverviewParts {
  const PatientOverviewParts({
    required this.ageYears,
    required this.dateOfBirth,
    required this.specialtyLabel,
    required this.lastActivityAt,
  });

  final int? ageYears;
  final Object? dateOfBirth;
  final String specialtyLabel;
  final Object? lastActivityAt;
}

/// Builds the parts from a [Patient] + [Specialty].
PatientOverviewParts partsFor(Patient patient, Specialty specialty) =>
    PatientOverviewParts(
      ageYears: patient.ageYears,
      dateOfBirth: patient.dateOfBirth,
      specialtyLabel: specialty.label,
      lastActivityAt: patient.lastActivityAt,
    );

/// Reads a memory item's headline for the overview header chip.
String memoryHeadline(ClinicalMemoryItem item) => item.content.headline;

/// Reads a fact's confidence band label.
String factConfidenceLabel(ClinicalFact fact) =>
    '${fact.confidenceBand.label} · ${fact.confidencePercent}';
