import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/animations/motion.dart';
import '../../core/models/medication.dart';
import '../../core/models/timeline_event.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/utils/date_format.dart';
import '../../shared/cards/clin_cards.dart';
import '../../shared/loading/states.dart';
import '../../shared/widgets/app_icons.dart';
import '../../shared/widgets/primitives.dart';
import '../../shared/widgets/sheets.dart';
import '../overview/overview_tab_bodies.dart';
import '../state/feature_providers.dart';

/// Medication reconciliation — plan §9.9, template: reference screen 3's
/// boarding-pass card.
///
/// Copy rule (plan §6.6 rule 3): neutral text only. Two records are shown side
/// by side and **neither** is marked correct. No recommendation verbs.
class MedicationReconciliationScreen extends ConsumerStatefulWidget {
  const MedicationReconciliationScreen({
    super.key,
    required this.patientId,
    required this.groupKey,
    this.medicationName,
  });

  final String patientId;

  /// Canonical medication name (the backend also accepts the DB `group_key`).
  final String groupKey;
  final String? medicationName;

  @override
  ConsumerState<MedicationReconciliationScreen> createState() =>
      _MedicationReconciliationScreenState();
}

class _MedicationReconciliationScreenState
    extends ConsumerState<MedicationReconciliationScreen> {
  final List<ChecklistItemModel> _tasks = <ChecklistItemModel>[
    const ChecklistItemModel(
        id: 'confirm', label: 'Confirm current instruction'),
    const ChecklistItemModel(id: 'adherence', label: 'Check patient adherence'),
    const ChecklistItemModel(id: 'update', label: 'Update record'),
  ];

  String get _name =>
      widget.medicationName ??
      widget.groupKey.split(RegExp(r'[_\s]')).map((String p) {
        return p.isEmpty ? p : '${p[0].toUpperCase()}${p.substring(1)}';
      }).join(' ');

  @override
  Widget build(BuildContext context) {
    final ({String patientId, String groupKey}) args =
        (patientId: widget.patientId, groupKey: widget.groupKey);
    final AsyncValue<List<MedicationHistoryEntry>> async =
        ref.watch(medicationHistoryProvider(args));
    final ClinicalIssue? issue =
        ref.read(issuesProvider(widget.patientId).notifier).conflictFor(
              widget.groupKey,
            );

    final List<MedicationHistoryEntry> history =
        async.valueOrNull ?? const <MedicationHistoryEntry>[];

    // Newest first: the two most recent instructions are the ones to compare.
    final MedicationHistoryEntry? a = history.isNotEmpty ? history[0] : null;
    final MedicationHistoryEntry? b = history.length > 1 ? history[1] : null;
    final bool changed = a != null && b != null && _differs(a, b);

    return Scaffold(
      backgroundColor: AppColors.bgCanvas,
      body: SafeArea(
        bottom: false,
        child: Column(
          children: <Widget>[
            TopBar(
              title: _name,
              subtitle: history.isEmpty
                  ? 'No history recorded'
                  : AppDate.range(history.last.documentDate, a?.documentDate),
              onLeadingTap: () => context.pop(),
              trailing: <Widget>[
                CircleIconButton(
                  icon: 'bell',
                  tooltip: 'Alerts are not configured in this prototype',
                  onTap: () => AppSnack.show(
                      context, 'Alerts are not configured in this prototype.'),
                ),
                CircleIconButton(
                  icon: 'moreVertical',
                  tooltip: 'More',
                  onTap: () => _showMore(context),
                ),
              ],
            ),
            Expanded(
              child: async.isLoading
                  ? const Padding(
                      padding:
                          EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
                      child: Column(
                        children: <Widget>[
                          SkeletonCard(height: 220),
                          SizedBox(height: AppSpacing.lg),
                          SkeletonCard(height: 160),
                        ],
                      ),
                    )
                  : async.hasError
                      ? ErrorStateView(
                          message: 'We couldn\'t load the record history.',
                          onRetry: () =>
                              ref.invalidate(medicationHistoryProvider(args)),
                        )
                      : ListView(
                          padding: EdgeInsets.zero,
                          children: <Widget>[
                            // ── TicketCard
                            SectionReveal(
                              index: 0,
                              child: Padding(
                                padding: const EdgeInsets.fromLTRB(
                                  AppSpacing.screenH,
                                  AppSpacing.md,
                                  AppSpacing.screenH,
                                  0,
                                ),
                                child: TicketCard(
                                  headerLabel: 'MEDICATION CHANGE',
                                  statusLabel: changed ? 'Conflict' : 'Review',
                                  headerIconName: 'pill',
                                  connectorIconName:
                                      changed ? 'replace' : 'arrowLeftRight',
                                  connectorCaption:
                                      changed ? 'Changed' : 'Compare',
                                  leftBlock: a == null
                                      ? null
                                      : TicketRouteBlock(
                                          label: 'Source A',
                                          code: a.frequencyCodeLabel,
                                          time: a.doseText,
                                          date:
                                              AppDate.dayMonth(a.documentDate),
                                          codeStyle: AppTypography.numberLarge,
                                        ),
                                  rightBlock: b == null
                                      ? null
                                      : TicketRouteBlock(
                                          label: 'Source B',
                                          code: b.frequencyCodeLabel,
                                          time: b.doseText,
                                          date:
                                              AppDate.dayMonth(b.documentDate),
                                          alignEnd: true,
                                          codeStyle: AppTypography.numberLarge,
                                        ),
                                  keyValues: <Widget>[
                                    KeyValueCell(label: 'Drug', value: _name),
                                    KeyValueCell(
                                        label: 'Strength',
                                        value:
                                            a?.strengthLine ?? 'Not recorded'),
                                    KeyValueCell(
                                      label: 'Records',
                                      value: '${history.length}',
                                    ),
                                  ],
                                  trailingTile: EvidenceTile(
                                    label: 'Evidence',
                                    onTap: () => _openEvidence(context),
                                  ),
                                ),
                              ),
                            ),

                            // ── Neutral copy
                            SectionReveal(
                              index: 1,
                              child: Padding(
                                padding: const EdgeInsets.fromLTRB(
                                  AppSpacing.screenH,
                                  AppSpacing.md,
                                  AppSpacing.screenH,
                                  0,
                                ),
                                child: ClinNoticeBanner(
                                  message: changed
                                      ? 'Two records contain different instructions for $_name. '
                                          'Both are shown as recorded; ClinSync does not decide which applies.'
                                      : 'Records for $_name were found in ${history.length} source'
                                          '${history.length == 1 ? '' : 's'}. Compare them against the original documents.',
                                  tone: changed
                                      ? ClinNoticeTone.warning
                                      : ClinNoticeTone.neutral,
                                  icon: changed ? 'alertTriangle' : 'info',
                                ),
                              ),
                            ),

                            // ── Both source documents
                            SectionReveal(
                              index: 2,
                              child: Padding(
                                padding: const EdgeInsets.fromLTRB(
                                  AppSpacing.screenH,
                                  AppSpacing.lg,
                                  AppSpacing.screenH,
                                  AppSpacing.xs,
                                ),
                                child: Text('Source records',
                                    style: AppTypography.titleSection),
                              ),
                            ),
                            SectionReveal(
                              index: 3,
                              child: Padding(
                                padding: const EdgeInsets.symmetric(
                                    horizontal: AppSpacing.screenH),
                                child: Column(
                                  children: <Widget>[
                                    for (final MedicationHistoryEntry e
                                        in history)
                                      Padding(
                                        padding: const EdgeInsets.only(
                                            bottom: AppSpacing.xs),
                                        child: LinkRowCard(
                                          title: e.sourceDocumentFilename ??
                                              'Source record',
                                          label:
                                              '${AppDate.date(e.documentDate)} · ${e.frequencyCodeLabel}',
                                          meta: e.doseLine,
                                          thumbnailIcon: 'fileText',
                                          onTap: e.sourceDocumentId == null
                                              ? null
                                              : () => context.push(
                                                    '/documents/${Uri.encodeComponent(e.sourceDocumentId!)}'
                                                    '/processing?patient=${widget.patientId}',
                                                  ),
                                        ),
                                      ),
                                  ],
                                ),
                              ),
                            ),

                            // ── Clinician review checklist
                            SectionReveal(
                              index: 4,
                              child: Padding(
                                padding: const EdgeInsets.fromLTRB(
                                  AppSpacing.screenH,
                                  AppSpacing.md,
                                  AppSpacing.screenH,
                                  0,
                                ),
                                child: ChecklistCard(
                                  title: 'Clinician review',
                                  items: _tasks,
                                  countLabel:
                                      '${_tasks.where((ChecklistItemModel t) => t.done).length} of '
                                      '${_tasks.length} done',
                                  onItemToggle:
                                      (ChecklistItemModel item, bool value) {
                                    setState(() {
                                      final int i = _tasks.indexWhere(
                                          (ChecklistItemModel t) =>
                                              t.id == item.id);
                                      if (i != -1) {
                                        _tasks[i] = item.copyWith(done: value);
                                      }
                                    });
                                  },
                                ),
                              ),
                            ),

                            // ── Linked conflict
                            if (issue != null)
                              SectionReveal(
                                index: 5,
                                child: Padding(
                                  padding: const EdgeInsets.fromLTRB(
                                    AppSpacing.screenH,
                                    AppSpacing.md,
                                    AppSpacing.screenH,
                                    0,
                                  ),
                                  child: IssueCard(
                                    issue: issue,
                                    patientId: widget.patientId,
                                    compact: false,
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
        primaryLabel: 'View Evidence',
        primaryIcon: 'fileSearch',
        onPrimary: () => _openEvidence(context),
        extraSecondaryIcons: <Widget>[
          const SizedBox(width: AppSpacing.xs),
          CircleIconButton(
            icon: 'share',
            tooltip: 'Share source links',
            size: 56,
            iconSize: 22,
            onTap: () => AppSnack.show(
              context,
              'Sharing is not enabled in this prototype.',
            ),
          ),
        ],
      ),
    );
  }

  static bool _differs(MedicationHistoryEntry a, MedicationHistoryEntry b) =>
      a.frequencyCode != b.frequencyCode ||
      a.doseText != b.doseText ||
      a.strengthValue != b.strengthValue;

  void _openEvidence(BuildContext context) {
    final ({String patientId, String groupKey}) args =
        (patientId: widget.patientId, groupKey: widget.groupKey);
    final AsyncValue<List<MedicationHistoryEntry>> async =
        ref.read(medicationHistoryProvider(args));
    final List<MedicationHistoryEntry> history =
        async.valueOrNull ?? const <MedicationHistoryEntry>[];
    if (history.isEmpty) {
      AppSnack.error(context, 'No source facts are linked yet.');
      return;
    }
    context.push('/patients/${widget.patientId}/facts');
  }

  void _showMore(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: AppColors.bgCanvas,
      builder: (BuildContext sheetContext) => SheetScaffold(
        title: _name,
        subtitle: 'Reconciliation',
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            _ActionTile(
              iconName: 'history',
              label: 'Open timeline',
              onTap: () {
                Navigator.of(sheetContext).pop();
                context.push('/patients/${widget.patientId}/timeline');
              },
            ),
            _ActionTile(
              iconName: 'alertTriangle',
              label: 'Open review queue',
              onTap: () {
                Navigator.of(sheetContext).pop();
                context.push('/patients/${widget.patientId}/issues');
              },
            ),
            _ActionTile(
              iconName: 'sparkles',
              label: 'Generate brief',
              onTap: () {
                Navigator.of(sheetContext).pop();
                context.push('/patients/${widget.patientId}/brief');
              },
            ),
            const SizedBox(height: AppSpacing.md),
          ],
        ),
      ),
    );
  }
}

class _ActionTile extends StatelessWidget {
  const _ActionTile(
      {required this.iconName, required this.label, required this.onTap});

  final String iconName;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return PressScale(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(
            vertical: AppSpacing.sm, horizontal: AppSpacing.xs),
        child: Row(
          children: <Widget>[
            Icon(AppIcons.byName(iconName),
                size: 18, color: AppColors.textPrimary),
            const SizedBox(width: AppSpacing.sm),
            Text(label, style: AppTypography.bodyStrong),
            const Spacer(),
            Icon(AppIcons.byName('chevronRight'),
                size: 16, color: AppColors.textTertiary),
          ],
        ),
      ),
    );
  }
}
