import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/animations/motion.dart';
import '../../core/constants/enums.dart';
import '../../core/models/clinical_memory.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../shared/loading/states.dart';
import '../../shared/widgets/app_icons.dart';
import '../../shared/widgets/primitives.dart';
import '../consultation/consultation_screen.dart';
import '../state/feature_providers.dart';

/// Clinical memory — plan §9.18.
///
/// Visually distinct from AI facts: a white card with a `primary` left accent and
/// a check. Everything here is doctor-approved.
class ClinicalMemoryScreen extends ConsumerStatefulWidget {
  const ClinicalMemoryScreen(
      {super.key, required this.patientId, this.embedded = false});

  final String patientId;

  /// True when hosted inside the `Memory` shell tab (nav already present).
  final bool embedded;

  @override
  ConsumerState<ClinicalMemoryScreen> createState() =>
      _ClinicalMemoryScreenState();
}

class _ClinicalMemoryScreenState extends ConsumerState<ClinicalMemoryScreen> {
  int _type = 0;

  static const List<({String label, MemoryType? type})> _tabs =
      <({String label, MemoryType? type})>[
    (label: 'All', type: null),
    (label: 'Diagnoses', type: MemoryType.diagnosis),
    (label: 'Assessments', type: MemoryType.assessment),
    (label: 'Plan notes', type: MemoryType.planNote),
    (label: 'Medications', type: MemoryType.medication),
    (label: 'Allergies', type: MemoryType.allergy),
  ];

  @override
  Widget build(BuildContext context) {
    final AsyncSlice<List<ClinicalMemoryItem>> slice =
        ref.watch(memoryProvider(widget.patientId));
    final MemoryNotifier notifier =
        ref.read(memoryProvider(widget.patientId).notifier);
    final List<ClinicalMemoryItem> all =
        slice.data ?? const <ClinicalMemoryItem>[];
    final List<ClinicalMemoryItem> visible = notifier.byType(_tabs[_type].type);

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
                title: 'Clinical Memory',
                subtitle: widget.embedded
                    ? '${all.length} verified item${all.length == 1 ? '' : 's'}'
                    : '${all.length} doctor-approved item${all.length == 1 ? '' : 's'}',
                showLeading: !widget.embedded,
                leadingIcon: 'arrowLeft',
                onLeadingTap: () => context.pop(),
                trailing: <Widget>[
                  CircleIconButton(
                    icon: 'history',
                    tooltip: 'Memory history',
                    onTap: () => _showHistory(context),
                  ),
                  CircleIconButton(
                    icon: 'refreshCw',
                    tooltip: 'Refresh',
                    onTap: notifier.refresh,
                  ),
                ],
              ),
              if (all.isNotEmpty)
                const SectionReveal(
                  index: 0,
                  child: Padding(
                    padding: EdgeInsets.fromLTRB(
                      AppSpacing.screenH,
                      AppSpacing.sm,
                      AppSpacing.screenH,
                      0,
                    ),
                    child: Row(
                      children: <Widget>[
                        StatusPill(
                          label: 'Doctor approved',
                          variant: StatusPillVariant.approved,
                          icon: 'badgeCheck',
                        ),
                      ],
                    ),
                  ),
                ),
              if (all.isNotEmpty)
                SectionReveal(
                  index: 1,
                  child: Padding(
                    padding: const EdgeInsets.only(
                        top: AppSpacing.sm, bottom: AppSpacing.sm),
                    child: PillTabs(
                      labels: <String>[
                        for (final ({String label, MemoryType? type}) t
                            in _tabs)
                          t.label
                      ],
                      selectedIndex: _type,
                      onChanged: (int i) => setState(() => _type = i),
                    ),
                  ),
                ),
              if (slice.loading && !slice.hasData)
                const Padding(
                  padding: EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
                  child: Column(
                    children: <Widget>[
                      SkeletonCard(height: 110),
                      SizedBox(height: AppSpacing.xs),
                      SkeletonCard(height: 110),
                    ],
                  ),
                )
              else if (slice.hasError && all.isEmpty)
                ErrorStateView(
                  message: slice.error!.message,
                  onRetry: notifier.refresh,
                )
              else if (all.isEmpty)
                EmptyState(
                  icon: 'bookMarked',
                  title: 'No verified memory yet',
                  message:
                      'Approve a consultation to create the first verified clinical memory items.',
                  actionLabel: 'Open review queue',
                  onAction: () =>
                      context.push('/patients/${widget.patientId}/issues'),
                )
              else if (visible.isEmpty)
                EmptyState(
                  icon: 'bookMarked',
                  title: 'Nothing in “${_tabs[_type].label}”',
                  message: 'Switch tabs to see the other memory types.',
                  compact: true,
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
                            child: MemoryCard(
                                item: visible[i], patientId: widget.patientId),
                          ),
                        ),
                    ],
                  ),
                ),
              const SizedBox(height: AppSpacing.md),
              const ClinicalDisclaimer(),
              const SizedBox(height: AppSpacing.bottomSafe),
            ],
          ),
        ),
      ),
    );
  }

  void _showHistory(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.bgCanvas,
      builder: (BuildContext sheetContext) =>
          _MemoryHistorySheet(patientId: widget.patientId),
    );
  }
}

/// A verified memory item — `primary` left accent + check, per plan §9.18.
class MemoryCard extends StatelessWidget {
  const MemoryCard({super.key, required this.item, this.onTap, this.patientId});

  final ClinicalMemoryItem item;
  final VoidCallback? onTap;
  final String? patientId;

  @override
  Widget build(BuildContext context) {
    final List<String> bullets = item.content.bullets;
    return SurfaceCard(
      onTap: onTap,
      accentLeft: true,
      radius: 20,
      padding: const EdgeInsets.all(AppSpacing.cardGap),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Icon(AppIcons.byName('badgeCheck'),
                  size: 15, color: AppColors.primary),
              const SizedBox(width: 6),
              Text(
                item.memoryType.label.toUpperCase(),
                style: AppTypography.capsLabel.copyWith(
                  color: AppColors.textSecondary,
                  fontSize: 9.5,
                ),
              ),
              const Spacer(),
              const StatusPill(
                label: 'Verified',
                variant: StatusPillVariant.approved,
                icon: 'check',
                dense: true,
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            item.content.headline,
            style: AppTypography.titleCard.copyWith(fontSize: 14.5),
          ),
          if (bullets.length > 1) ...<Widget>[
            const SizedBox(height: 4),
            for (final String b in bullets.skip(1).take(4))
              Padding(
                padding: const EdgeInsets.only(bottom: 2),
                child: Text(b,
                    style: AppTypography.bodyBullet.copyWith(fontSize: 11.5)),
              ),
          ],
          const SizedBox(height: AppSpacing.xs),
          Row(
            children: <Widget>[
              Icon(AppIcons.byName('calendar'),
                  size: 11, color: AppColors.textTertiary),
              const SizedBox(width: 4),
              Text('Approved ${item.approvedLabel}',
                  style: AppTypography.caption.copyWith(fontSize: 10.5)),
              const Spacer(),
              if (item.sourceConsultationId != null)
                GestureDetector(
                  onTap: () {
                    final String? pid = patientId;
                    if (pid == null) return;
                    context.push(
                      '/patients/$pid/consultation/${Uri.encodeComponent(item.sourceConsultationId!)}',
                    );
                  },
                  child: Text(
                    'Source consultation',
                    style: AppTypography.link.copyWith(fontSize: 11),
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

/// `GET /patients/{id}/memory/history` — verified + unverified.
class _MemoryHistorySheet extends ConsumerWidget {
  const _MemoryHistorySheet({required this.patientId});

  final String patientId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<List<ClinicalMemoryItem>> async =
        ref.watch(memoryHistoryProvider(patientId));

    return DraggableScrollableSheet(
      initialChildSize: 0.7,
      minChildSize: 0.4,
      maxChildSize: 0.92,
      expand: false,
      builder: (BuildContext context, ScrollController controller) {
        return SheetScaffoldLite(
          title: 'Memory history',
          subtitle: 'Verified and unverified items',
          scrollController: controller,
          children: <Widget>[
            async.when(
              loading: () => const Padding(
                padding: EdgeInsets.all(AppSpacing.md),
                child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
              ),
              error: (Object e, StackTrace _) => const Padding(
                padding: EdgeInsets.all(AppSpacing.md),
                child: ClinNoticeBanner(
                  message: 'Could not load the memory history.',
                  tone: ClinNoticeTone.warning,
                  icon: 'alertTriangle',
                ),
              ),
              data: (List<ClinicalMemoryItem> items) => Column(
                children: <Widget>[
                  for (final ClinicalMemoryItem i in items)
                    Padding(
                      padding: const EdgeInsets.only(bottom: AppSpacing.xs),
                      child: MemoryCard(item: i, patientId: patientId),
                    ),
                ],
              ),
            ),
          ],
        );
      },
    );
  }
}
