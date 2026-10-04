import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/animations/motion.dart';
import '../../core/constants/app_assets.dart';
import '../../core/constants/enums.dart';
import '../../core/models/document.dart';
import '../../core/models/patient.dart';
import '../../core/repositories/providers.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../shared/cards/clin_cards.dart';
import '../../shared/loading/states.dart';
import '../../shared/widgets/app_icons.dart';
import '../../shared/widgets/primitives.dart';
import '../../shared/widgets/record_source_sheet.dart';
import '../../shared/widgets/sheets.dart';
import '../state/feature_providers.dart';
import 'overview_tab_bodies.dart';

/// Patient Overview — plan §9.3, template: reference screen 2.
///
/// Every element of the §6.1 screen-2 inventory is present: back/title/
/// bookmark/more bar, name + edit, meta line, avatar stack + `+N`, thumbnail,
/// the AI card (check, title, 2 meta lines, mini illustration, chevron) with its
/// 3-stat strip, pill tabs, rail with numbered green nodes + dotted line,
/// cards (icon, title, chevron, 2 bullets, thumbnail), the add row, and the
/// sticky green pill + circular filter.
class PatientOverviewScreen extends ConsumerStatefulWidget {
  const PatientOverviewScreen({super.key, required this.patientId});

  final String patientId;

  @override
  ConsumerState<PatientOverviewScreen> createState() =>
      _PatientOverviewScreenState();
}

class _PatientOverviewScreenState extends ConsumerState<PatientOverviewScreen> {
  int _tab = 0;
  bool _pinned = false;

  String get _id => widget.patientId;

  @override
  Widget build(BuildContext context) {
    final AsyncSlice<PatientOverview> slice = ref.watch(overviewProvider(_id));
    final AsyncSlice<List<ClinicalDocument>> docs =
        ref.watch(documentsProvider(_id));
    final Specialty specialty = ref.watch(specialtyProvider);
    final String? activeId = ref.watch(activePatientIdProvider);
    final int factCount = ref.watch(factsProvider(_id)).data?.length ?? 0;

    if (slice.loading && !slice.hasData) return const _OverviewSkeleton();

    if (slice.hasError && !slice.hasData) {
      return Scaffold(
        backgroundColor: AppColors.bgCanvas,
        body: SafeArea(
          child: Column(
            children: <Widget>[
              TopBar(
                  title: 'Patient Overview', onLeadingTap: () => context.pop()),
              Expanded(
                child: ErrorStateView(
                  message: slice.error!.message,
                  onRetry: () =>
                      ref.read(overviewProvider(_id).notifier).refresh(),
                ),
              ),
            ],
          ),
        ),
      );
    }

    final PatientOverview data = slice.data!;
    final Patient patient = data.patient;
    final List<ClinicalDocument> documents =
        docs.data ?? const <ClinicalDocument>[];
    final bool ready = data.hasClinicalFacts || factCount > 0;

    return Scaffold(
      backgroundColor: AppColors.bgCanvas,
      body: SafeArea(
        bottom: false,
        child: RefreshIndicator(
          color: AppColors.primary,
          onRefresh: () async {
            await Future.wait<void>(<Future<void>>[
              ref.read(overviewProvider(_id).notifier).refresh(),
              ref.read(documentsProvider(_id).notifier).refresh(),
              ref.read(factsProvider(_id).notifier).refresh(),
            ]);
          },
          child: ListView(
            padding: EdgeInsets.zero,
            children: <Widget>[
              // ── 1. TopBar: back · title · bookmark · more
              TopBar(
                title: 'Patient Overview',
                subtitle: patient.isDemo ? 'Demo patient' : null,
                onLeadingTap: () => context.pop(),
                trailing: <Widget>[
                  CircleIconButton(
                    icon: 'bookmark',
                    tooltip: _pinned ? 'Unpin patient' : 'Pin patient',
                    color: _pinned ? AppColors.primary : AppColors.textPrimary,
                    background:
                        _pinned ? AppColors.primarySoft : AppColors.surface,
                    onTap: () => setState(() => _pinned = !_pinned),
                  ),
                  CircleIconButton(
                    icon: 'moreVertical',
                    tooltip: 'More',
                    onTap: () => _showMoreSheet(context, patient),
                  ),
                ],
              ),

              // ── 2. HeaderBlock
              SectionReveal(
                index: 0,
                child: Padding(
                  padding: const EdgeInsets.only(top: AppSpacing.xs),
                  child: HeaderBlock(
                    name: patient.fullName,
                    metaLine: overviewMetaLine(partsFor(patient, specialty)),
                    documentTypeIcons: documentGlyphs(documents),
                    documentOverflow: documents.length,
                    onOverflowTap: () =>
                        context.push('/patients/$_id/documents'),
                    thumbnailIcon: documents.isEmpty
                        ? 'fileText'
                        : documents.first.documentType.icon,
                    thumbnailAsset: documents.isEmpty
                        ? kPatientAmbientImages.first
                        : documentAmbient(0),
                    chips: <Widget>[
                      if (patient.id == activeId)
                        const StatusPill(
                          label: 'Active patient',
                          variant: StatusPillVariant.approved,
                          dense: true,
                        ),
                      StatusPill(
                        label:
                            '${data.sourceCount} record${data.sourceCount == 1 ? '' : 's'}',
                        variant: StatusPillVariant.neutral,
                        icon: 'files',
                        dense: true,
                      ),
                      if (data.memorySummary.isNotEmpty)
                        const StatusPill(
                          label: 'Memory approved',
                          variant: StatusPillVariant.approved,
                          icon: 'badgeCheck',
                          dense: true,
                        ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: AppSpacing.lg),

              // ── 3. InsightCard with the 3-stat strip
              SectionReveal(
                index: 1,
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.screenH),
                  child: InsightCard(
                    title: ready
                        ? 'Clinical Context Ready'
                        : 'No Clinical Facts Yet',
                    metaLine1: ready
                        ? 'Evidence-linked • Source-traceable'
                        : 'Upload or scan a record to begin',
                    metaLine2: ready
                        ? 'Unverified until approved'
                        : 'Nothing has been extracted yet',
                    trailingIconName:
                        data.openIssueTotal > 0 ? 'alertTriangle' : 'mapPin',
                    statusPill: data.openIssueTotal > 0
                        ? StatusPill(
                            label: '${data.openIssueTotal} open',
                            variant: data.highSeverityOpen > 0
                                ? StatusPillVariant.conflict
                                : StatusPillVariant.needsReview,
                            icon: 'alertTriangle',
                            dense: true,
                          )
                        : const StatusPill(
                            label: 'No open issues',
                            variant: StatusPillVariant.approved,
                            icon: 'checkCircle',
                            dense: true,
                          ),
                    onTap: () => context.push('/patients/$_id/issues'),
                    stats: <Widget>[
                      StatItem(
                        iconName: 'files',
                        label: 'Documents',
                        value: '${data.sourceCount}',
                        onTap: () => context.push('/patients/$_id/documents'),
                      ),
                      StatItem(
                        iconName: 'sparkles',
                        label: 'Clinical Facts',
                        value: '$factCount',
                        onTap: () => context.push('/patients/$_id/facts'),
                      ),
                      StatItem(
                        iconName: 'alertTriangle',
                        label: 'Open Issues',
                        value: '${data.openIssueTotal}',
                        onTap: () => context.push('/patients/$_id/issues'),
                      ),
                    ],
                  ),
                ),
              ),

              // ── 4. PillTabs
              SectionReveal(
                index: 2,
                child: Padding(
                  padding: const EdgeInsets.only(
                      top: AppSpacing.lg, bottom: AppSpacing.sm),
                  child: PillTabs(
                    labels: kOverviewTabLabels,
                    selectedIndex: _tab,
                    onChanged: (int i) => setState(() => _tab = i),
                  ),
                ),
              ),

              // ── 5. Tab content
              SectionReveal(
                index: 3,
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.screenH),
                  child: AnimatedSwitcher(
                    duration: const Duration(milliseconds: 200),
                    switchInCurve: Curves.easeOut,
                    transitionBuilder: (Widget child, Animation<double> anim) =>
                        FadeTransition(opacity: anim, child: child),
                    child: KeyedSubtree(
                      key: ValueKey<int>(_tab),
                      child: OverviewTabBody(
                        patientId: _id,
                        tab: OverviewTab.values[_tab],
                      ),
                    ),
                  ),
                ),
              ),

              // ── 6. AddRow `+ Add Record`
              SectionReveal(
                index: 4,
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(
                    AppSpacing.screenH,
                    AppSpacing.xs,
                    AppSpacing.screenH,
                    0,
                  ),
                  child: Align(
                    alignment: Alignment.centerLeft,
                    child: AddRow(
                      label: 'Add Record',
                      onTap: () => showRecordSourceSheet(context, ref, _id),
                    ),
                  ),
                ),
              ),

              const SizedBox(height: AppSpacing.md),
              const ClinicalDisclaimer(),
              const SizedBox(height: AppSpacing.stickyBarHeight),
            ],
          ),
        ),
      ),

      // ── 7. StickyActionBar
      bottomNavigationBar: StickyActionBar(
        primaryLabel: 'Generate Brief',
        primaryIcon: 'sparkles',
        enabled: ready,
        tooltip: ready
            ? null
            : 'Upload a record first — there are no clinical facts yet',
        onPrimary: () => context.push('/patients/$_id/brief'),
        secondaryIcon: 'sliders',
        secondaryTooltip: 'Clinical specialty',
        onSecondary: () => context.push('/specialty?patient=$_id'),
      ),
    );
  }

  void _showMoreSheet(BuildContext context, Patient patient) {
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: AppColors.bgCanvas,
      builder: (BuildContext sheetContext) => SheetScaffold(
        title: patient.fullName,
        subtitle: '${patient.ageLabel} • ${patient.sexLabel}',
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            _MoreTile(
              iconName: 'history',
              label: 'Full timeline',
              onTap: () {
                Navigator.of(sheetContext).pop();
                context.push('/patients/$_id/timeline');
              },
            ),
            _MoreTile(
              iconName: 'pill',
              label: 'All medications',
              onTap: () {
                Navigator.of(sheetContext).pop();
                context.push('/patients/$_id/medications');
              },
            ),
            _MoreTile(
              iconName: 'flaskConical',
              label: 'Investigations',
              onTap: () {
                Navigator.of(sheetContext).pop();
                context.push('/patients/$_id/investigations');
              },
            ),
            _MoreTile(
              iconName: 'bookMarked',
              label: 'Clinical memory',
              onTap: () {
                Navigator.of(sheetContext).pop();
                context.push('/patients/$_id/memory');
              },
            ),
            _MoreTile(
              iconName: 'alertTriangle',
              label: 'Review queue',
              onTap: () {
                Navigator.of(sheetContext).pop();
                context.push('/patients/$_id/issues');
              },
            ),
            const SizedBox(height: AppSpacing.md),
          ],
        ),
      ),
    );
  }
}

class _MoreTile extends StatelessWidget {
  const _MoreTile(
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

class _OverviewSkeleton extends StatelessWidget {
  const _OverviewSkeleton();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      backgroundColor: AppColors.bgCanvas,
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            TopBar(title: 'Patient Overview'),
            Padding(
              padding: EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
              child: SkeletonCard(height: 110),
            ),
            SizedBox(height: AppSpacing.lg),
            Padding(
              padding: EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
              child: SkeletonCard(height: 190),
            ),
            SizedBox(height: AppSpacing.lg),
            Padding(
              padding: EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
              child: SkeletonRail(),
            ),
          ],
        ),
      ),
    );
  }
}
