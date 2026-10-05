import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/animations/motion.dart';
import '../../core/constants/enums.dart';
import '../../core/models/doctor_brief.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../shared/cards/ambient_background.dart';
import '../../shared/cards/clin_cards.dart';
import '../../shared/loading/states.dart';
import '../../shared/widgets/primitives.dart';
import '../state/feature_providers.dart';
import '../trends/lab_trend_screen.dart';

/// 60-second brief — plan §9.14.
///
/// Scannable, not an essay. Template: reference screen 3's pass card + screen 2's
/// AI card. Every statement carries an evidence chip, and the disclaimer is
/// always visible (plan §6.6 rule 6).
class BriefScreen extends ConsumerStatefulWidget {
  const BriefScreen({super.key, required this.patientId, this.specialty});

  final String patientId;
  final String? specialty;

  @override
  ConsumerState<BriefScreen> createState() => _BriefScreenState();
}

class _BriefScreenState extends ConsumerState<BriefScreen> {
  @override
  void initState() {
    super.initState();
    final String? s = widget.specialty;
    if (s != null && s.isNotEmpty) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        ref.read(briefProvider(widget.patientId).notifier).specialty = s;
        ref.read(briefProvider(widget.patientId).notifier).refresh();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final BriefNotifier notifier =
        ref.read(briefProvider(widget.patientId).notifier);
    final AsyncSlice<DoctorBrief> slice =
        ref.watch(briefProvider(widget.patientId));
    final Specialty specialty = ref.watch(specialtyProvider);
    final DoctorBrief? brief = slice.data;

    return Scaffold(
      backgroundColor: AppColors.bgCanvas,
      body: SafeArea(
        bottom: false,
        child: Column(
          children: <Widget>[
            Stack(
              children: <Widget>[
                const Positioned(
                    top: 0,
                    left: 0,
                    right: 0,
                    child: AmbientRibbon(height: 96)),
                TopBar(
                  title: '60-Second Brief',
                  subtitle: brief == null
                      ? specialty.label
                      : '${brief.specialtyLabel} • ${brief.generatedLabel}',
                  onLeadingTap: () => context.pop(),
                  trailing: <Widget>[
                    CircleIconButton(
                      icon: 'refreshCw',
                      tooltip: 'Regenerate',
                      onTap: () => ref
                          .read(briefProvider(widget.patientId).notifier)
                          .refresh(),
                    ),
                  ],
                ),
              ],
            ),
            Expanded(
              child: switch ((
                slice.loading && !slice.hasData,
                slice.hasError && !slice.hasData,
                brief
              )) {
                (true, _, _) => _StagedLoading(stage: notifier.stage),
                (_, true, _) => ErrorStateView(
                    message: slice.error!.message,
                    onRetry: () => ref
                        .read(briefProvider(widget.patientId).notifier)
                        .refresh(),
                    title: 'The brief could not be prepared',
                  ),
                (_, _, null) => const EmptyState(
                    icon: 'fileText',
                    title: 'No brief yet',
                    message:
                        'Generate a brief to get a 60-second clinical summary of this patient\'s records.',
                  ),
                (_, _, final DoctorBrief b) =>
                  _BriefBody(brief: b, patientId: widget.patientId),
              },
            ),
          ],
        ),
      ),
      bottomNavigationBar: StickyActionBar(
        primaryLabel: 'Start Consultation',
        primaryIcon: 'pencil',
        enabled: brief != null && !slice.loading,
        onPrimary: () => context.push(
          '/patients/${widget.patientId}/consultation'
          '?specialty=${brief?.specialty.wire ?? specialty.wire}',
        ),
        secondaryIcon: 'sliders',
        secondaryTooltip: 'Change specialty',
        onSecondary: () => context.push(
            '/specialty?patient=${widget.patientId}&title=Brief specialty'),
      ),
    );
  }
}

/// `Collecting evidence → Comparing records → Preparing brief`.
class _StagedLoading extends StatelessWidget {
  const _StagedLoading({required this.stage});

  final BriefStage stage;

  @override
  Widget build(BuildContext context) {
    final int active = stage == BriefStage.idle
        ? 0
        : stage == BriefStage.collecting
            ? 1
            : stage == BriefStage.comparing
                ? 2
                : 3;

    return ListView(
      padding: EdgeInsets.zero,
      children: <Widget>[
        const SectionReveal(
          index: 0,
          child: Padding(
            padding: EdgeInsets.fromLTRB(
              AppSpacing.screenH,
              AppSpacing.md,
              AppSpacing.screenH,
              0,
            ),
            child: SkeletonCard(height: 150),
          ),
        ),
        const SizedBox(height: AppSpacing.lg),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
          child: Column(
            children: <Widget>[
              for (int i = 1; i <= 3; i++)
                Padding(
                  padding: const EdgeInsets.only(bottom: AppSpacing.xs),
                  child: ClinNoticeBanner(
                    message: <String>[
                      'Collecting evidence',
                      'Comparing records',
                      'Preparing brief',
                    ][i - 1],
                    icon: i == active ? 'loader' : 'checkCircle',
                    tone: i == active
                        ? ClinNoticeTone.primary
                        : ClinNoticeTone.neutral,
                  ),
                ),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.lg),
        const Padding(
          padding: EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
          child: Column(
            children: <Widget>[
              SkeletonCard(height: 120),
              SizedBox(height: AppSpacing.xs),
              SkeletonCard(height: 120),
            ],
          ),
        ),
      ],
    );
  }
}

class _BriefBody extends StatelessWidget {
  const _BriefBody({required this.brief, required this.patientId});

  final DoctorBrief brief;
  final String patientId;

  void _evidence(BuildContext context, List<String> ids) {
    if (ids.isEmpty) return;
    context.push('/facts/${Uri.encodeComponent(ids.first)}/evidence');
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: EdgeInsets.zero,
      children: <Widget>[
        // ── TicketCard-style summary header
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
              headerLabel: 'CLINICAL BRIEF',
              statusLabel:
                  brief.servedByTemplate ? 'From records' : 'AI-generated',
              headerIconName:
                  brief.servedByTemplate ? 'clipboardList' : 'sparkles',
              connectorIconName: 'clipboardList',
              connectorCaption: 'Summary',
              leftBlock: TicketRouteBlock(
                label: 'Chief complaint',
                code: _shortCode(brief.chiefComplaint?.text ?? ''),
                time: brief.chiefComplaint?.hasText == true
                    ? null
                    : 'Not documented',
                codeStyle: AppTypography.numberLarge.copyWith(fontSize: 22),
              ),
              rightBlock: TicketRouteBlock(
                label: 'Sources',
                code: '${brief.evidenceCount}',
                time: brief.contradictions.isEmpty
                    ? 'No conflicts'
                    : '${brief.contradictions.length} flagged',
                alignEnd: true,
                codeStyle: AppTypography.numberLarge.copyWith(fontSize: 22),
              ),
              keyValues: <Widget>[
                KeyValueCell(label: 'Patient', value: brief.patientName ?? '—'),
                KeyValueCell(label: 'Specialty', value: brief.specialtyLabel),
                KeyValueCell(label: 'Generated', value: brief.generatedLabel),
              ],
              trailingTile: EvidenceTile(
                label: 'Sources',
                onTap: () {
                  if (brief.evidenceShortcuts.isEmpty) {
                    AppSnack.error(context,
                        'No source shortcuts are attached to this brief.');
                    return;
                  }
                  _evidence(context,
                      <String>[brief.evidenceShortcuts.first.evidenceId]);
                },
              ),
            ),
          ),
        ),

        // ── AI / unverified marker + disclaimer
        //
        // When the backend assembled the brief from records with its
        // deterministic template (no model involved), saying "AI-generated"
        // would be inaccurate. Both variants still withhold approval: nothing
        // here becomes clinical memory until the doctor approves it (§6.6).
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
              message: brief.servedByTemplate
                  ? 'Assembled directly from the records · Unverified. '
                      'Nothing here becomes clinical memory until you approve it.'
                  : 'AI-generated · Unverified. '
                      'Nothing here becomes clinical memory until you approve it.',
              tone: ClinNoticeTone.primary,
              icon: 'shieldAlert',
            ),
          ),
        ),

        // ── Chief complaint in full
        if (brief.chiefComplaint?.hasText == true)
          SectionReveal(
            index: 2,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.screenH,
                AppSpacing.md,
                AppSpacing.screenH,
                0,
              ),
              child: BriefSectionCard(
                title: 'CHIEF COMPLAINT',
                iconName: 'stethoscope',
                trailing: EvidenceChip(
                  onTap: () =>
                      _evidence(context, brief.chiefComplaint!.evidenceIds),
                ),
                child:
                    Text(brief.chiefComplaint!.text, style: AppTypography.body),
              ),
            ),
          ),

        // ── Relevant history
        if (brief.relevantHistory.isNotEmpty)
          SectionReveal(
            index: 3,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.screenH,
                AppSpacing.sm,
                AppSpacing.screenH,
                0,
              ),
              child: BriefSectionCard(
                title: 'RELEVANT HISTORY',
                iconName: 'history',
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    for (final BriefHistoryItem h in brief.relevantHistory)
                      Padding(
                        padding: const EdgeInsets.only(bottom: AppSpacing.xs),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            Expanded(
                                child: Text(h.text,
                                    style: AppTypography.bodyBullet)),
                            const SizedBox(width: AppSpacing.xs),
                            EvidenceChip(
                              onTap: () => _evidence(context, h.evidenceIds),
                            ),
                          ],
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ),

        // ── Current medications (with conflict tags)
        if (brief.currentMedications.isNotEmpty)
          SectionReveal(
            index: 4,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.screenH,
                AppSpacing.sm,
                AppSpacing.screenH,
                0,
              ),
              child: BriefSectionCard(
                title: 'CURRENT MEDICATIONS',
                iconName: 'pill',
                child: Column(
                  children: <Widget>[
                    for (final BriefMedication m in brief.currentMedications)
                      Padding(
                        padding: const EdgeInsets.only(bottom: AppSpacing.xs),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: <Widget>[
                                  Text(m.name,
                                      style: AppTypography.bodyStrong
                                          .copyWith(fontSize: 13.5)),
                                  Text(m.doseLine,
                                      style: AppTypography.bodyBullet
                                          .copyWith(fontSize: 11.5)),
                                  if (m.conflictFlag)
                                    const Padding(
                                      padding: EdgeInsets.only(top: 4),
                                      child: StatusPill(
                                        label: 'Conflicting records',
                                        variant: StatusPillVariant.conflict,
                                        icon: 'alertTriangle',
                                        dense: true,
                                      ),
                                    ),
                                ],
                              ),
                            ),
                            const SizedBox(width: AppSpacing.xs),
                            EvidenceChip(
                                onTap: () => _evidence(context, m.evidenceIds)),
                          ],
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ),

        // ── Allergies — `Not documented` shown explicitly
        SectionReveal(
          index: 5,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.screenH,
              AppSpacing.sm,
              AppSpacing.screenH,
              0,
            ),
            child: BriefSectionCard(
              title: 'ALLERGIES',
              iconName: 'alertTriangle',
              child: brief.allergies.isEmpty
                  ? Row(
                      children: <Widget>[
                        const StatusPill(
                          label: 'Not documented',
                          variant: StatusPillVariant.needsReview,
                          dense: true,
                        ),
                        const SizedBox(width: AppSpacing.xs),
                        Expanded(
                          child: Text(
                            'No allergy record was found in the uploaded files.',
                            style: AppTypography.bodyBullet
                                .copyWith(fontSize: 11.5),
                          ),
                        ),
                      ],
                    )
                  : Column(
                      children: <Widget>[
                        for (final BriefAllergy a in brief.allergies)
                          Padding(
                            padding: const EdgeInsets.only(bottom: 4),
                            child: Row(
                              children: <Widget>[
                                Expanded(
                                  child: Text(
                                    a.isEmpty ? 'Not documented' : a.text,
                                    style: AppTypography.bodyBullet,
                                  ),
                                ),
                                EvidenceChip(
                                    onTap: () =>
                                        _evidence(context, a.evidenceIds)),
                              ],
                            ),
                          ),
                      ],
                    ),
            ),
          ),
        ),

        // ── Recent investigations
        if (brief.recentInvestigations.isNotEmpty)
          SectionReveal(
            index: 6,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.screenH,
                AppSpacing.sm,
                AppSpacing.screenH,
                0,
              ),
              child: BriefSectionCard(
                title: 'RECENT INVESTIGATIONS',
                iconName: 'flaskConical',
                child: Column(
                  children: <Widget>[
                    for (final BriefInvestigation i
                        in brief.recentInvestigations)
                      Padding(
                        padding: const EdgeInsets.only(bottom: AppSpacing.xs),
                        child: Row(
                          children: <Widget>[
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: <Widget>[
                                  Text(i.test,
                                      style: AppTypography.bodyStrong
                                          .copyWith(fontSize: 13)),
                                  Text(
                                    '${i.valueLabel} • ${i.date ?? 'date not recorded'}',
                                    style: AppTypography.bodyBullet
                                        .copyWith(fontSize: 11.5),
                                  ),
                                ],
                              ),
                            ),
                            if (i.abnormal)
                              const StatusPill(
                                label: 'Out of range',
                                variant: StatusPillVariant.needsReview,
                                dense: true,
                              ),
                            const SizedBox(width: 4),
                            EvidenceChip(
                                onTap: () => _evidence(context, i.evidenceIds)),
                          ],
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ),

        // ── Important trends with mini sparklines
        if (brief.importantTrends.isNotEmpty)
          SectionReveal(
            index: 7,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.screenH,
                AppSpacing.sm,
                AppSpacing.screenH,
                0,
              ),
              child: BriefSectionCard(
                title: 'IMPORTANT TRENDS',
                iconName: 'trendingUp',
                child: Column(
                  children: <Widget>[
                    for (final BriefTrend t in brief.importantTrends)
                      Padding(
                        padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            TrendSparkline(
                              values: t.series
                                  .where((BriefTrendPoint p) => p.hasValue)
                                  .map((BriefTrendPoint p) => p.value)
                                  .toList(growable: false),
                            ),
                            const SizedBox(width: AppSpacing.sm),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: <Widget>[
                                  Text(
                                    t.test,
                                    style: AppTypography.bodyStrong
                                        .copyWith(fontSize: 13),
                                  ),
                                  const SizedBox(height: 1),
                                  Text(
                                    t.description ??
                                        'No trend description available.',
                                    style: AppTypography.bodyBullet
                                        .copyWith(fontSize: 11.5),
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(width: 4),
                            EvidenceChip(
                                onTap: () => _evidence(context, t.evidenceIds)),
                          ],
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ),

        // ── Attention items
        if (brief.attentionItems.isNotEmpty)
          SectionReveal(
            index: 8,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.screenH,
                AppSpacing.sm,
                AppSpacing.screenH,
                0,
              ),
              child: BriefSectionCard(
                title: 'ATTENTION ITEMS',
                iconName: 'alertTriangle',
                child: Column(
                  children: <Widget>[
                    for (final BriefAttention a in brief.attentionItems)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 6),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            if (a.severity != null)
                              Padding(
                                padding:
                                    const EdgeInsets.only(top: 2, right: 6),
                                child: StatusPill(
                                  label: a.severity!.label,
                                  variant: a.severity == Severity.high
                                      ? StatusPillVariant.conflict
                                      : StatusPillVariant.needsReview,
                                  dense: true,
                                ),
                              ),
                            Expanded(
                                child: Text(a.text,
                                    style: AppTypography.bodyBullet)),
                            const SizedBox(width: 4),
                            EvidenceChip(
                                onTap: () => _evidence(context, a.evidenceIds)),
                          ],
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ),

        // ── Contradictions
        if (brief.contradictions.isNotEmpty)
          SectionReveal(
            index: 9,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.screenH,
                AppSpacing.sm,
                AppSpacing.screenH,
                0,
              ),
              child: BriefSectionCard(
                title: 'CONTRADICTIONS',
                iconName: 'gitCompare',
                child: Column(
                  children: <Widget>[
                    for (final BriefContradiction c in brief.contradictions)
                      Padding(
                        padding: const EdgeInsets.only(bottom: AppSpacing.xs),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            Text(c.text, style: AppTypography.bodyBullet),
                            if (c.sources.isNotEmpty)
                              Padding(
                                padding: const EdgeInsets.only(
                                    top: 4, left: AppSpacing.xs),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: <Widget>[
                                    for (final String s in c.sources)
                                      Text(
                                        '• $s',
                                        style: AppTypography.caption
                                            .copyWith(fontSize: 11),
                                      ),
                                  ],
                                ),
                              ),
                            if (c.issueId != null)
                              GestureDetector(
                                onTap: () =>
                                    context.push('/patients/$patientId/issues'),
                                child: Padding(
                                  padding: const EdgeInsets.only(top: 4),
                                  child: Text(
                                    'Open in review queue',
                                    style: AppTypography.link
                                        .copyWith(fontSize: 11.5),
                                  ),
                                ),
                              ),
                          ],
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ),

        // ── Missing information — phrased as a question to the doctor
        if (brief.missingInformation.isNotEmpty)
          SectionReveal(
            index: 10,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.screenH,
                AppSpacing.sm,
                AppSpacing.screenH,
                0,
              ),
              child: ChecklistCard(
                title: 'MISSING INFORMATION',
                items: <ChecklistItemModel>[
                  for (final BriefMissing m in brief.missingInformation)
                    ChecklistItemModel(
                      id: m.prompt,
                      label: _asQuestion(m.prompt),
                      detail: m.reason,
                    ),
                ],
                onHeaderTap: () => context.push('/patients/$patientId/issues'),
              ),
            ),
          ),

        // ── Evidence shortcuts as chips
        if (brief.evidenceShortcuts.isNotEmpty)
          SectionReveal(
            index: 11,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.screenH,
                AppSpacing.sm,
                AppSpacing.screenH,
                0,
              ),
              child: BriefSectionCard(
                title: 'EVIDENCE',
                iconName: 'fileSearch',
                child: Wrap(
                  spacing: AppSpacing.xs,
                  runSpacing: AppSpacing.xs,
                  children: <Widget>[
                    for (final EvidenceShortcut e in brief.evidenceShortcuts)
                      EvidenceChip(
                        label: e.page == null
                            ? e.label
                            : '${e.label} · p${e.page}',
                        onTap: () => _evidence(context, <String>[e.evidenceId]),
                      ),
                  ],
                ),
              ),
            ),
          ),

        // ── Footer disclaimer
        ClinicalDisclaimer(text: brief.disclaimerText),
        const SizedBox(height: AppSpacing.stickyBarHeight),
      ],
    );
  }

  /// Plan §6.6 rule 4: missing information is phrased as a question.
  static String _asQuestion(String prompt) {
    String p = prompt.trim();
    if (p.toLowerCase().startsWith('potentially missing:')) {
      p = p.substring('potentially missing:'.length).trim();
    }
    if (p.endsWith('?')) return p;
    return '$p?';
  }

  static String _shortCode(String text) {
    final String t = text.trim();
    if (t.isEmpty) return '—';
    if (t.length <= 22) return t;
    return '${t.substring(0, 21)}…';
  }
}
