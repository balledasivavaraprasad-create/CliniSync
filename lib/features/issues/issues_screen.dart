import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/animations/motion.dart';
import '../../core/constants/enums.dart';
import '../../core/models/specialty.dart';
import '../../core/models/timeline_event.dart';
import '../../core/repositories/providers.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_radii.dart';
import '../../core/theme/app_shadows.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../shared/loading/states.dart';
import '../../shared/widgets/app_icons.dart';
import '../../shared/widgets/primitives.dart';
import '../overview/overview_tab_bodies.dart';
import '../state/feature_providers.dart';

/// Clinical review queue — plan §9.12.
///
/// Template: reference screen 3's checklist + progress ring, and screen 2's
/// cards. Conflicts, missing information and low-confidence facts.
class IssuesScreen extends ConsumerStatefulWidget {
  const IssuesScreen({super.key, required this.patientId});

  final String patientId;

  @override
  ConsumerState<IssuesScreen> createState() => _IssuesScreenState();
}

class _IssuesScreenState extends ConsumerState<IssuesScreen> {
  int _tab = 0;
  bool _recomputing = false;

  static const List<String> _tabs = <String>[
    'Conflicts',
    'Missing',
    'Low confidence'
  ];

  @override
  Widget build(BuildContext context) {
    final AsyncSlice<List<ClinicalIssue>> slice =
        ref.watch(issuesProvider(widget.patientId));
    final IssuesNotifier notifier =
        ref.read(issuesProvider(widget.patientId).notifier);
    final List<ClinicalIssue> all = slice.data ?? const <ClinicalIssue>[];

    final List<ClinicalIssue> visible = switch (_tab) {
      0 => notifier.conflicts,
      1 => notifier.missing,
      _ => notifier.lowConfidence,
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
                title: 'Review queue',
                subtitle: '${notifier.open.length} open · ${all.length} total',
                onLeadingTap: () => context.pop(),
                trailing: <Widget>[
                  CircleIconButton(
                    icon: 'refreshCw',
                    tooltip: 'Re-check',
                    onTap: _recomputing ? null : () => _recompute(notifier),
                  ),
                ],
              ),

              // ── Review progress
              SectionReveal(
                index: 0,
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(
                    AppSpacing.screenH,
                    AppSpacing.md,
                    AppSpacing.screenH,
                    0,
                  ),
                  child: ReviewProgressStrip(
                    reviewed: notifier.reviewedCount,
                    total: all.length,
                    onTap: () => setState(() => _tab = 0),
                  ),
                ),
              ),

              if (_recomputing)
                const Padding(
                  padding: EdgeInsets.fromLTRB(
                    AppSpacing.screenH,
                    AppSpacing.sm,
                    AppSpacing.screenH,
                    0,
                  ),
                  child: ClinNoticeBanner(
                    message: 'Re-checking the records…',
                    icon: 'loader',
                    tone: ClinNoticeTone.primary,
                  ),
                ),

              SectionReveal(
                index: 1,
                child: Padding(
                  padding: const EdgeInsets.only(
                      top: AppSpacing.lg, bottom: AppSpacing.sm),
                  child: PillTabs(
                    labels: _tabs,
                    selectedIndex: _tab,
                    onChanged: (int i) => setState(() => _tab = i),
                  ),
                ),
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
              else if (visible.isEmpty)
                EmptyState(
                  icon: 'shieldCheck',
                  title: all.isEmpty
                      ? 'Nothing needs review'
                      : 'Nothing in “${_tabs[_tab]}”',
                  message: all.isEmpty
                      ? 'No open conflicts or missing information were detected in the records processed so far.'
                      : 'Switch tabs to see the other review categories.',
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
                            child: IssueCard(
                                issue: visible[i], patientId: widget.patientId),
                          ),
                        ),
                    ],
                  ),
                ),

              const SizedBox(height: AppSpacing.md),
              const ClinicalDisclaimer(),
              const SizedBox(height: AppSpacing.stickyBarHeight),
            ],
          ),
        ),
      ),
      bottomNavigationBar: StickyActionBar(
        primaryLabel: 'Generate Brief',
        primaryIcon: 'sparkles',
        enabled: all.isNotEmpty,
        onPrimary: () => context.push('/patients/${widget.patientId}/brief'),
        secondaryIcon: 'sliders',
        secondaryTooltip: 'Clinical specialty',
        onSecondary: () =>
            context.push('/specialty?patient=${widget.patientId}'),
      ),
    );
  }

  Future<void> _recompute(IssuesNotifier notifier) async {
    setState(() => _recomputing = true);
    try {
      await notifier.recompute();
      if (mounted) AppSnack.show(context, 'Review queue refreshed');
    } catch (_) {
      if (mounted) AppSnack.error(context, 'Could not re-check right now.');
    } finally {
      if (mounted) setState(() => _recomputing = false);
    }
  }
}

/// Specialty selection — plan §9.13, template: reference screen 1's tiles.
class SpecialtyScreen extends ConsumerStatefulWidget {
  const SpecialtyScreen({super.key, this.patientId, this.title = 'Specialty'});

  final String? patientId;
  final String title;

  @override
  ConsumerState<SpecialtyScreen> createState() => _SpecialtyScreenState();
}

class _SpecialtyScreenState extends ConsumerState<SpecialtyScreen> {
  /// Wire id, matching what `POST /brief` expects.
  late String _selected = ref.read(specialtyProvider).wire;

  /// Human label for the current selection, taken from the backend catalogue
  /// when it is loaded and from the bundled mirror otherwise.
  String get _label {
    final List<SpecialtyOption> catalog =
        ref.read(specialtyCatalogProvider).value ??
            SpecialtyOption.mirroringBackend();
    for (final SpecialtyOption o in catalog) {
      if (o.id == _selected) return o.name;
    }
    return Specialty.fromWire(_selected).label;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bgCanvas,
      body: SafeArea(
        bottom: false,
        child: Column(
          children: <Widget>[
            TopBar(
              title: widget.title,
              onLeadingTap: () => context.pop(),
            ),
            Expanded(
              child: ListView(
                padding: EdgeInsets.zero,
                children: <Widget>[
                  SectionReveal(
                    index: 0,
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(
                        AppSpacing.screenH,
                        AppSpacing.md,
                        AppSpacing.screenH,
                        AppSpacing.xs,
                      ),
                      child: Text(
                        'Choose a specialty',
                        style: AppTypography.titlePage,
                      ),
                    ),
                  ),
                  SectionReveal(
                    index: 1,
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(
                        AppSpacing.screenH,
                        0,
                        AppSpacing.screenH,
                        AppSpacing.md,
                      ),
                      child: Text(
                        'The brief is prepared with this specialty in mind. It changes what is emphasised, not what was recorded.',
                        style: AppTypography.body
                            .copyWith(color: AppColors.textSecondary),
                      ),
                    ),
                  ),
                  SectionReveal(
                    index: 2,
                    child: LayoutBuilder(
                      builder:
                          (BuildContext context, BoxConstraints constraints) {
                        const double gap = AppSpacing.xs;
                        final int columns = constraints.maxWidth > 400 ? 3 : 2;
                        final double width =
                            (constraints.maxWidth - gap * (columns - 1)) /
                                columns;
                        final List<SpecialtyOption> catalog =
                            ref.watch(specialtyCatalogProvider).value ??
                                SpecialtyOption.mirroringBackend();
                        return Padding(
                          padding: const EdgeInsets.symmetric(
                              horizontal: AppSpacing.screenH),
                          child: Wrap(
                            spacing: gap,
                            runSpacing: gap,
                            children: <Widget>[
                              for (int i = 0; i < catalog.length; i++)
                                SizedBox(
                                  width: width,
                                  child: SectionReveal(
                                    index: i,
                                    child: _SpecialtyTile(
                                      option: catalog[i],
                                      selected: catalog[i].id == _selected,
                                      onTap: () => setState(
                                          () => _selected = catalog[i].id),
                                    ),
                                  ),
                                ),
                            ],
                          ),
                        );
                      },
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
        primaryLabel: 'Continue',
        primaryIcon: 'check',
        onPrimary: () async {
          await ref.read(specialtyProvider.notifier).select(
                Specialty.fromWire(_selected),
              );
          if (!context.mounted) return;
          final String? patientId = widget.patientId;
          if (patientId != null) {
            context.pushReplacement('/patients/$patientId/brief?specialty=$_selected');
          } else {
            AppSnack.show(context, 'Specialty set to $_label');
            context.pop();
          }
        },
      ),
    );
  }
}

class _SpecialtyTile extends StatelessWidget {
  const _SpecialtyTile(
      {required this.option, required this.selected, required this.onTap});

  /// From `GET /specialties` — the backend owns this list (see
  /// [SpecialtyRepository]).
  final SpecialtyOption option;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return PressScale(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(
            vertical: AppSpacing.lg, horizontal: AppSpacing.sm),
        decoration: BoxDecoration(
          color: selected ? AppColors.primarySoft : AppColors.surface,
          borderRadius: AppRadii.allTile,
          border: Border.all(
            color: selected ? AppColors.primary : Colors.transparent,
            width: 1.6,
          ),
          boxShadow: selected ? null : AppShadows.tile,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Stack(
              clipBehavior: Clip.none,
              children: <Widget>[
                Icon(
                  AppIcons.byName(option.icon),
                  size: 26,
                  color:
                      selected ? AppColors.primaryDark : AppColors.textPrimary,
                ),
                if (selected)
                  Positioned(
                    right: -8,
                    top: -6,
                    child: Container(
                      width: 16,
                      height: 16,
                      decoration: const BoxDecoration(
                        color: AppColors.primary,
                        shape: BoxShape.circle,
                      ),
                      alignment: Alignment.center,
                      child: Icon(
                        AppIcons.byName('check'),
                        size: 10,
                        color: AppColors.onPrimary,
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: AppSpacing.xs),
            Text(
              option.name,
              textAlign: TextAlign.center,
              style: AppTypography.tileLabel.copyWith(
                color:
                    selected ? AppColors.primaryDark : AppColors.textSecondary,
                fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
