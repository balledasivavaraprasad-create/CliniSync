import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/animations/motion.dart';
import '../../core/constants/enums.dart';
import '../../core/models/investigation.dart';
import '../../core/models/medication.dart';
import '../../core/models/timeline_event.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/utils/date_format.dart';
import '../../shared/cards/clin_cards.dart';
import '../../shared/loading/states.dart';
import '../../shared/widgets/primitives.dart';
import '../overview/overview_tab_bodies.dart';
import '../state/feature_providers.dart';

/// Full-screen timeline — plan §9.7.
///
/// `TimelineRail` + `TimelineCard` per event, type filter, and undated events
/// grouped under `Undated`.
class TimelineScreen extends ConsumerStatefulWidget {
  const TimelineScreen({super.key, required this.patientId});

  final String patientId;

  @override
  ConsumerState<TimelineScreen> createState() => _TimelineScreenState();
}

class _TimelineScreenState extends ConsumerState<TimelineScreen> {
  int _filter = 0;

  static const List<String> _filters = <String>[
    'All',
    'Medication',
    'Investigation',
    'Diagnosis',
    'Approved',
  ];

  static String? _typeFor(int index) => switch (index) {
        0 => null,
        1 => 'medication_start',
        2 => 'investigation',
        3 => 'diagnosis',
        _ => 'approved_note',
      };

  @override
  Widget build(BuildContext context) {
    final AsyncSlice<List<TimelineEvent>> slice =
        ref.watch(timelineProvider(widget.patientId));
    final TimelineNotifier notifier =
        ref.read(timelineProvider(widget.patientId).notifier);

    final List<TimelineEvent> all = slice.data ?? const <TimelineEvent>[];
    final String? type = _typeFor(_filter);
    final List<TimelineEvent> visible = type == null
        ? all
        : all
            .where((TimelineEvent e) => e.eventType.wire == type)
            .toList(growable: false);
    final List<TimelineEvent> dated = visible
        .where((TimelineEvent e) => !e.isUndated)
        .toList(growable: false);
    final List<TimelineEvent> undated =
        visible.where((TimelineEvent e) => e.isUndated).toList(growable: false);

    return Scaffold(
      backgroundColor: AppColors.bgCanvas,
      body: SafeArea(
        bottom: false,
        child: RefreshIndicator(
          color: AppColors.primary,
          onRefresh: notifier.refresh,
          child: ListView(
            padding: EdgeInsets.zero,
            children: <Widget>[
              TopBar(
                title: 'Timeline',
                subtitle:
                    '${all.length} event${all.length == 1 ? '' : 's'} from source records',
                onLeadingTap: () => context.pop(),
                trailing: <Widget>[
                  CircleIconButton(
                    icon: 'refreshCw',
                    tooltip: 'Refresh',
                    onTap: notifier.refresh,
                  ),
                ],
              ),
              SectionReveal(
                index: 0,
                child: Padding(
                  padding: const EdgeInsets.only(
                      top: AppSpacing.sm, bottom: AppSpacing.md),
                  child: PillTabs(
                    labels: _filters,
                    selectedIndex: _filter,
                    onChanged: (int i) => setState(() => _filter = i),
                  ),
                ),
              ),
              if (slice.loading && !slice.hasData)
                const Padding(
                  padding: EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
                  child: SkeletonRail(),
                )
              else if (slice.hasError && all.isEmpty)
                ErrorStateView(
                  message: slice.error!.message,
                  onRetry: notifier.refresh,
                )
              else if (visible.isEmpty)
                const EmptyState(
                  icon: 'history',
                  title: 'No events yet',
                  message:
                      'The timeline is built from the records you upload. Nothing has been dated yet.',
                  compact: false,
                )
              else ...<Widget>[
                Padding(
                  padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.screenH),
                  child: Column(
                    children: <Widget>[
                      for (int i = 0; i < dated.length; i++)
                        SectionReveal(
                          index: i,
                          child: Padding(
                            padding:
                                const EdgeInsets.only(bottom: AppSpacing.sm),
                            child: DatedTimelineEntry(
                              date: dated[i].eventDate,
                              isFirst: i == 0,
                              isLast: undated.isEmpty && i == dated.length - 1,
                              child: TimelineCard(
                                iconName: dated[i].eventType.icon,
                                title: dated[i].title,
                                bullet1: dated[i].summary,
                                bullet2: dated[i].sourceDocumentId == null
                                    ? 'No source document linked'
                                    : 'Linked to a source record',
                                onTap: dated[i].relatedFactIds.isEmpty
                                    ? null
                                    : () => context.push(
                                          '/facts/${Uri.encodeComponent(dated[i].relatedFactIds.first)}'
                                          '/evidence',
                                        ),
                                thumbnailIcon: dated[i].eventType.icon,
                              ),
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
                if (undated.isNotEmpty) ...<Widget>[
                  Padding(
                    padding: const EdgeInsets.fromLTRB(
                      AppSpacing.screenH,
                      AppSpacing.sm,
                      AppSpacing.screenH,
                      AppSpacing.xs,
                    ),
                    child: Text(
                      AppDate.undatedLabel.toUpperCase(),
                      style: AppTypography.capsLabel
                          .copyWith(color: AppColors.textSecondary),
                    ),
                  ),
                  Padding(
                    padding: const EdgeInsets.symmetric(
                        horizontal: AppSpacing.screenH),
                    child: Column(
                      children: <Widget>[
                        for (int i = 0; i < undated.length; i++)
                          SectionReveal(
                            index: dated.length + i,
                            child: Padding(
                              padding:
                                  const EdgeInsets.only(bottom: AppSpacing.xs),
                              child: TimelineCard(
                                iconName: undated[i].eventType.icon,
                                title: undated[i].title,
                                bullet1: undated[i].summary,
                                bullet2: 'No date recorded in the source',
                                thumbnailIcon: undated[i].eventType.icon,
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                ],
              ],
              const SizedBox(height: AppSpacing.md),
              const ClinicalDisclaimer(),
              const SizedBox(height: AppSpacing.xxl),
            ],
          ),
        ),
      ),
    );
  }
}

/// Full-screen medications — plan §9.8.
class MedicationsScreen extends ConsumerStatefulWidget {
  const MedicationsScreen({super.key, required this.patientId});

  final String patientId;

  @override
  ConsumerState<MedicationsScreen> createState() => _MedicationsScreenState();
}

class _MedicationsScreenState extends ConsumerState<MedicationsScreen> {
  int _tab = 0;

  static const List<String> _tabs = <String>[
    'Current',
    'Previous',
    'Uncertain'
  ];

  @override
  Widget build(BuildContext context) {
    final AsyncSlice<List<Medication>> slice =
        ref.watch(medicationsProvider(widget.patientId));
    final MedicationsNotifier notifier =
        ref.read(medicationsProvider(widget.patientId).notifier);
    final List<Medication> all = slice.data ?? const <Medication>[];
    final List<Medication> visible = switch (_tab) {
      0 => notifier.byStatus(MedicationStatus.current),
      1 => notifier.byStatus(MedicationStatus.previous),
      _ => notifier.byStatus(MedicationStatus.uncertain),
    };

    return Scaffold(
      backgroundColor: AppColors.bgCanvas,
      body: SafeArea(
        bottom: false,
        child: RefreshIndicator(
          color: AppColors.primary,
          onRefresh: notifier.refresh,
          child: ListView(
            padding: EdgeInsets.zero,
            children: <Widget>[
              TopBar(
                title: 'Medications',
                subtitle:
                    '${all.length} instruction${all.length == 1 ? '' : 's'} extracted',
                onLeadingTap: () => context.pop(),
                trailing: <Widget>[
                  CircleIconButton(
                    icon: 'refreshCw',
                    tooltip: 'Refresh',
                    onTap: notifier.refresh,
                  ),
                ],
              ),
              SectionReveal(
                index: 0,
                child: Padding(
                  padding: const EdgeInsets.only(
                      top: AppSpacing.sm, bottom: AppSpacing.md),
                  child: PillTabs(
                    labels: _tabs,
                    selectedIndex: _tab,
                    onChanged: (int i) => setState(() => _tab = i),
                  ),
                ),
              ),
              if (notifier.conflicts.isNotEmpty)
                SectionReveal(
                  index: 1,
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(
                      AppSpacing.screenH,
                      0,
                      AppSpacing.screenH,
                      AppSpacing.sm,
                    ),
                    child: ClinNoticeBanner(
                      message: '${notifier.conflicts.length} medication'
                          '${notifier.conflicts.length == 1 ? '' : 's'} have conflicting records. '
                          'Both sources are shown side by side — nothing is resolved automatically.',
                      tone: ClinNoticeTone.warning,
                      icon: 'alertTriangle',
                    ),
                  ),
                ),
              if (slice.loading && !slice.hasData)
                const Padding(
                  padding: EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
                  child: Column(
                    children: <Widget>[
                      SkeletonCard(height: 108),
                      SizedBox(height: AppSpacing.xs),
                      SkeletonCard(height: 108),
                    ],
                  ),
                )
              else if (slice.hasError && all.isEmpty)
                ErrorStateView(
                  message: slice.error!.message,
                  onRetry: notifier.refresh,
                )
              else if (visible.isEmpty)
                EmptyState(
                  icon: 'pill',
                  title: 'Nothing in “${_tabs[_tab]}”',
                  message: all.isEmpty
                      ? 'Medication instructions appear here once a prescription is processed.'
                      : 'Switch tabs to see the other statuses.',
                )
              else
                Padding(
                  padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.screenH),
                  child: Column(
                    children: <Widget>[
                      for (int i = 0; i < visible.length; i++)
                        SectionReveal(
                          index: i,
                          child: Padding(
                            padding:
                                const EdgeInsets.only(bottom: AppSpacing.xs),
                            child: MedicationCard(
                              medication: visible[i],
                              onTap: () => context.push(
                                '/patients/${widget.patientId}/medications/'
                                '${Uri.encodeComponent(visible[i].historyPathSegment)}'
                                '/reconcile?name=${Uri.encodeQueryComponent(visible[i].displayName)}',
                              ),
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              const SizedBox(height: AppSpacing.md),
              const ClinicalDisclaimer(),
              const SizedBox(height: AppSpacing.xxl),
            ],
          ),
        ),
      ),
    );
  }
}

/// Full-screen investigations — plan §9.10.
class InvestigationsScreen extends ConsumerWidget {
  const InvestigationsScreen({super.key, required this.patientId});

  final String patientId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncSlice<List<Investigation>> slice =
        ref.watch(investigationsProvider(patientId));
    final InvestigationsNotifier notifier =
        ref.read(investigationsProvider(patientId).notifier);
    final List<Investigation> all = slice.data ?? const <Investigation>[];

    return Scaffold(
      backgroundColor: AppColors.bgCanvas,
      body: SafeArea(
        bottom: false,
        child: RefreshIndicator(
          color: AppColors.primary,
          onRefresh: notifier.refresh,
          child: ListView(
            padding: EdgeInsets.zero,
            children: <Widget>[
              TopBar(
                title: 'Investigations',
                subtitle:
                    '${all.length} test${all.length == 1 ? '' : 's'} · latest values',
                onLeadingTap: () => context.pop(),
                trailing: <Widget>[
                  CircleIconButton(
                    icon: 'refreshCw',
                    tooltip: 'Refresh',
                    onTap: notifier.refresh,
                  ),
                ],
              ),
              if (slice.loading && !slice.hasData)
                const Padding(
                  padding: EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
                  child: Column(
                    children: <Widget>[
                      SkeletonCard(height: 130),
                      SizedBox(height: AppSpacing.xs),
                      SkeletonCard(height: 130),
                    ],
                  ),
                )
              else if (slice.hasError && all.isEmpty)
                ErrorStateView(
                  message: slice.error!.message,
                  onRetry: notifier.refresh,
                )
              else if (all.isEmpty)
                const EmptyState(
                  icon: 'flaskConical',
                  title: 'No investigations recorded',
                  message:
                      'Lab results appear here with their reference ranges and dates.',
                )
              else
                Padding(
                  padding: const EdgeInsets.fromLTRB(
                    AppSpacing.screenH,
                    AppSpacing.md,
                    AppSpacing.screenH,
                    0,
                  ),
                  child: InvestigationGrid(
                    patientId: patientId,
                    investigations: all,
                  ),
                ),
              const SizedBox(height: AppSpacing.md),
              const ClinicalDisclaimer(),
              const SizedBox(height: AppSpacing.xxl),
            ],
          ),
        ),
      ),
    );
  }
}
