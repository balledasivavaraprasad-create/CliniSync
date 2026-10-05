import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/animations/motion.dart';
import '../../core/constants/app_assets.dart';
import '../../core/constants/enums.dart';
import '../../core/models/patient.dart';
import '../../core/repositories/providers.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_radii.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/utils/debounce.dart';
import '../../shared/cards/ambient_background.dart';
import '../../shared/cards/clin_cards.dart';
import '../../shared/loading/states.dart';
import '../../shared/widgets/app_icons.dart';
import '../../shared/widgets/primitives.dart';
import '../../shared/widgets/settings_sheet.dart';
import '../../shared/widgets/sheets.dart';
import '../state/feature_providers.dart';

/// Home — plan §9.1, template: reference screen 1.
///
/// All 12 elements of the §6.1 screen-1 inventory are present: menu button,
/// specialty circle (the avatar slot), 3-line two-tone serif headline,
/// subtitle, hero art, overlapping search pill with green mic, section header +
/// `See all`, edge-bleeding image cards with scrim + arrow, page dots, Quick
/// Actions 4 tiles, and the AI banner.
class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  final TextEditingController _search = TextEditingController();
  final Debouncer _debounce = Debouncer();
  final PageController _carousel =
      PageController(viewportFraction: AppSpacing.patientCardViewportFraction);
  String _query = '';
  int _page = 0;

  @override
  void dispose() {
    _search.dispose();
    _debounce.dispose();
    _carousel.dispose();
    super.dispose();
  }

  void _onSearchChanged(String value) {
    _debounce(() {
      if (mounted) setState(() => _query = value);
    });
  }

  @override
  Widget build(BuildContext context) {
    final AsyncSlice<List<Patient>> slice = ref.watch(patientsProvider);
    final String? activeId = ref.watch(activePatientIdProvider);
    final Specialty specialty = ref.watch(specialtyProvider);

    final List<Patient> patients = slice.hasData
        ? (slice.data!.where((Patient p) => p.id == activeId).isNotEmpty
            ? <Patient>[
                slice.data!.firstWhere((Patient p) => p.id == activeId),
                ...slice.data!.where((Patient p) => p.id != activeId),
              ]
            : slice.data!)
        : const <Patient>[];

    final List<Patient> visible =
        _query.trim().isEmpty ? patients : _filtered(patients);

    return Scaffold(
      backgroundColor: AppColors.bgCanvas,
      body: SafeArea(
        bottom: false,
        child: RefreshIndicator(
          color: AppColors.primary,
          onRefresh: () async => ref.read(patientsProvider.notifier).refresh(),
          child: CustomScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            slivers: <Widget>[
              // ── Top row: menu + specialty circle
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(
                    AppSpacing.screenH,
                    AppSpacing.xs,
                    AppSpacing.screenH,
                    0,
                  ),
                  child: Row(
                    children: <Widget>[
                      CircleIconButton(
                        icon: 'menu',
                        tooltip: 'Settings',
                        onTap: () => showSettingsSheet(context, ref),
                      ),
                      const Spacer(),
                      // Replaces the reference avatar: no login, so the top-right
                      // circle is the current specialty (plan §9.1).
                      PressScale(
                        onTap: () => unawaited(context.push('/specialty')),
                        child: Container(
                          width: 44,
                          height: 44,
                          decoration: const BoxDecoration(
                            color: AppColors.primarySoft,
                            shape: BoxShape.circle,
                          ),
                          alignment: Alignment.center,
                          child: Icon(
                            AppIcons.byName(specialty.icon),
                            size: 20,
                            color: AppColors.primaryDark,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              // ── Hero: ambient art + 3-line two-tone serif headline + the search
              //    pill straddling the bottom edge (reference §6.1 elements 3–6).
              //    The pill lives *inside* the hero's stack, exactly as the
              //    reference has it, so its stacking can never depend on sliver
              //    paint order.
              SliverToBoxAdapter(
                child: SectionReveal(
                  index: 0,
                  child: AmbientParallax(
                    // `clipBehavior: Clip.none` so the search pill can straddle
                    // the hero's bottom edge — `Stack` hard-clips overflowing
                    // positioned children by default.
                    child: Stack(
                      clipBehavior: Clip.none,
                      children: <Widget>[
                        // Ambient art. Its lower third fades into `bgCanvas`, so
                        // there is no visible seam and the headline keeps AA
                        // contrast (plan §7.8).
                        const Positioned.fill(
                          child: ClipRRect(
                            borderRadius: BorderRadius.vertical(
                              bottom: Radius.circular(AppRadii.xl),
                            ),
                            child: AmbientLayer(
                              height: 320,
                              videoAsset: AppAssets.heroVideo,
                              posterAsset: AppAssets.heroPoster,
                              // The ambient loop is a bright chrome render on
                              // near-white, so it needs a heavier wash than a
                              // painterly background would: 0.52 keeps it
                              // legible as motion and depth while the
                              // headline stays the focal point (§6.1 el. 5,
                              // §7.8).
                              washOpacity: 0.52,
                              videoOpacity: 0.55,
                              videoFraction: 0.62,
                              fit: BoxFit.cover,
                            ),
                          ),
                        ),
                        Padding(
                          padding: const EdgeInsets.fromLTRB(
                            AppSpacing.screenH,
                            AppSpacing.lg,
                            AppSpacing.screenH,
                            AppSpacing.xxxl + AppSpacing.xs,
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: <Widget>[
                              // §6.4 text replacement table. Animated line by
                              // line with the landing page's masked
                              // `translateY(115%)` wipe
                              // (`style.css:290-295`, landing §7) — the
                              // headline is the one element the reference
                              // page makes a performance of.
                              LineReveal(
                                lineHeight: AppTypography.displayHero.fontSize! *
                                    AppTypography.displayHero.height!,
                                lines: <Widget>[
                                  Text(
                                    'Every Record,',
                                    style: AppTypography.displayHero,
                                  ),
                                  Text(
                                    'Clinically',
                                    style: AppTypography.displayHeroAccent,
                                  ),
                                  Text(
                                    'Connected.',
                                    style: AppTypography.displayHeroAccent,
                                  ),
                                ],
                              ),
                              const SizedBox(height: AppSpacing.sm),
                              // Held back until the headline has landed, the
                              // way the landing page sequences hero copy.
                              SectionReveal(
                                index: 0,
                                delay: const Duration(milliseconds: 700),
                                offset: 8,
                                child: Text(
                                  'AI-assisted clinical context,\nalways under your review.',
                                  style: AppTypography.body.copyWith(
                                    color: AppColors.textSecondary,
                                    height: 1.5,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                        // Search pill: the mic is Voice Note (plan §9.1).
                        Positioned(
                          left: AppSpacing.screenH,
                          right: AppSpacing.screenH,
                          bottom: -AppSpacing.xxl,
                          child: SearchPill(
                            hint: 'Search patients or records',
                            controller: _search,
                            onChanged: _onSearchChanged,
                            onMicTap: () async {
                              final String? id =
                                  await requireActivePatient(context, ref);
                              if (id == null || !context.mounted) return;
                              await context.push('/voice/$id');
                            },
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),

              // ── Spacing that the overlapping search pill occupies.
              const SliverToBoxAdapter(child: SizedBox(height: AppSpacing.xxl)),

              // ── Recent Patients + See all
              SliverToBoxAdapter(
                child: SectionReveal(
                  index: 1,
                  child: SectionHeader(
                    title: 'Recent Patients',
                    linkLabel: 'See all',
                    onLinkTap: () => context.go('/patients'),
                  ),
                ),
              ),

              // ── Edge-bleeding patient carousel + page dots
              SliverToBoxAdapter(
                child: SectionReveal(
                  index: 2,
                  child: _PatientCarousel(
                    patients: visible,
                    loading: slice.loading && !slice.hasData,
                    error: slice.error,
                    activeId: activeId,
                    controller: _carousel,
                    page: _page,
                    onPage: (int i) => setState(() => _page = i),
                    onRetry: () =>
                        ref.read(patientsProvider.notifier).refresh(),
                  ),
                ),
              ),

              // ── Quick Actions
              const SliverToBoxAdapter(
                child: SectionReveal(
                  index: 4,
                  child: Padding(
                    padding: EdgeInsets.only(top: AppSpacing.xs),
                    child: SectionHeader(title: 'Quick Actions'),
                  ),
                ),
              ),
              SliverToBoxAdapter(
                child: SectionReveal(
                  index: 4,
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(
                      AppSpacing.screenH,
                      AppSpacing.sm,
                      AppSpacing.screenH,
                      0,
                    ),
                    child: _QuickActions(),
                  ),
                ),
              ),

              // ── AI banner
              SliverToBoxAdapter(
                child: SectionReveal(
                  index: 5,
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(
                      AppSpacing.screenH,
                      AppSpacing.sectionGap,
                      AppSpacing.screenH,
                      AppSpacing.md,
                    ),
                    child: AIBanner(
                      title: 'Let AI prepare your consultation',
                      subtitle:
                          'Evidence-linked. Reviewed by you. Verified on approval.',
                      onTap: () async {
                        final String? id =
                            await requireActivePatient(context, ref);
                        if (id == null || !context.mounted) return;
                        await context.push('/patients/$id/brief');
                      },
                    ),
                  ),
                ),
              ),

              const SliverToBoxAdapter(
                  child: SizedBox(height: AppSpacing.bottomSafe)),
            ],
          ),
        ),
      ),
    );
  }

  List<Patient> _filtered(List<Patient> patients) {
    final String q = _query.trim().toLowerCase();
    if (q.isEmpty) return patients;
    return patients
        .where((Patient p) =>
            p.fullName.toLowerCase().contains(q) ||
            p.ageLabel.toLowerCase().contains(q))
        .toList(growable: false);
  }
}

/// 3-tall-card carousel that bleeds to the screen edge; the third is cut.
class _PatientCarousel extends ConsumerWidget {
  const _PatientCarousel({
    required this.patients,
    required this.loading,
    required this.error,
    required this.activeId,
    required this.controller,
    required this.page,
    required this.onPage,
    required this.onRetry,
  });

  final List<Patient> patients;
  final bool loading;
  final Object? error;
  final String? activeId;
  final PageController controller;
  final int page;
  final ValueChanged<int> onPage;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (loading) {
      return const SizedBox(
        height: AppSpacing.patientCardHeight + 8,
        child: Row(
          children: <Widget>[
            SizedBox(width: AppSpacing.screenH),
            SkeletonPatientCard(),
            SizedBox(width: AppSpacing.carouselGap),
            SkeletonPatientCard(),
            SizedBox(width: AppSpacing.carouselGap),
            SkeletonPatientCard(),
          ],
        ),
      );
    }

    if (error != null && patients.isEmpty) {
      return ErrorStateView(
        message: 'Could not load patients.',
        onRetry: onRetry,
        compact: true,
      );
    }

    if (patients.isEmpty) {
      // Empty state: a PatientCard-shaped "create your first patient" card.
      return Padding(
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
        child: PatientCard(
          name: 'Add a patient',
          subtitle: 'Tap to create the first record',
          monogram: '+',
          onTap: () => showCreatePatientSheet(context, ref),
        ),
      );
    }

    return Column(
      children: <Widget>[
        SizedBox(
          height: AppSpacing.patientCardHeight,
          child: NotificationListener<ScrollNotification>(
            onNotification: (ScrollNotification n) {
              if (n is ScrollEndNotification &&
                  n.metrics.axis == Axis.horizontal) {
                final int index =
                    (controller.page ?? controller.initialPage.toDouble())
                        .round();
                if (index != page) onPage(index);
              }
              return false;
            },
            child: PageView.builder(
              controller: controller,
              padEnds: false,
              itemCount: patients.length,
              itemBuilder: (BuildContext context, int i) {
                final Patient p = patients[i];
                return Padding(
                  padding: EdgeInsets.only(
                    left: i == 0 ? AppSpacing.screenH : AppSpacing.carouselGap,
                    right: AppSpacing.carouselGap,
                  ),
                  child: PatientCard(
                    name: p.fullName,
                    subtitle: p.ageLabel,
                    monogram: p.monogram,
                    imageAsset:
                        kPatientAmbientImages[i % kPatientAmbientImages.length],
                    badgeLabel: p.id == activeId ? 'Active' : null,
                    onTap: () =>
                        openPatientOverview(context, ref, p.id, p.fullName),
                  ),
                );
              },
            ),
          ),
        ),
        PageDots(
          count: patients.length.clamp(0, 3),
          activeIndex: page.clamp(0, 2),
          onTap: (int i) => controller.animateToPage(
            i,
            duration: const Duration(milliseconds: 320),
            curve: Curves.easeOutCubic,
          ),
        ),
      ],
    );
  }
}

/// 4-up row of `QuickActionTile`s — §6.4 mapping.
class _QuickActions extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: <Widget>[
        QuickActionTile(
          iconName: 'fileUp',
          label: 'Upload\nRecord',
          onTap: () async {
            final String? id = await requireActivePatient(context, ref);
            if (id == null || !context.mounted) return;
            await context.push('/patients/$id/documents');
          },
        ),
        QuickActionTile(
          iconName: 'camera',
          label: 'Scan\nDocument',
          onTap: () async {
            final String? id = await requireActivePatient(context, ref);
            if (id == null || !context.mounted) return;
            await context.push('/camera/$id');
          },
        ),
        QuickActionTile(
          iconName: 'mic',
          label: 'Voice\nNote',
          onTap: () async {
            final String? id = await requireActivePatient(context, ref);
            if (id == null || !context.mounted) return;
            await context.push('/voice/$id');
          },
        ),
        QuickActionTile(
          iconName: 'fileText',
          label: 'Doctor\nBrief',
          onTap: () async {
            final String? id = await requireActivePatient(context, ref);
            if (id == null || !context.mounted) return;
            await context.push('/patients/$id/brief');
          },
        ),
      ],
    );
  }
}
