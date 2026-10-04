import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/animations/motion.dart';
import '../../core/constants/app_assets.dart';
import '../../core/models/patient.dart';
import '../../core/repositories/providers.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../shared/cards/clin_cards.dart';
import '../../shared/loading/states.dart';
import '../../shared/widgets/primitives.dart';
import '../../shared/widgets/sheets.dart';
import '../state/feature_providers.dart';

/// Patient list & create — plan §9.2.
class PatientListScreen extends ConsumerStatefulWidget {
  const PatientListScreen({super.key});

  @override
  ConsumerState<PatientListScreen> createState() => _PatientListScreenState();
}

class _PatientListScreenState extends ConsumerState<PatientListScreen> {
  String _query = '';

  @override
  Widget build(BuildContext context) {
    final AsyncSlice<List<Patient>> slice = ref.watch(patientsProvider);
    final String? activeId = ref.watch(activePatientIdProvider);

    final List<Patient> all = slice.data ?? const <Patient>[];
    final List<Patient> visible = _filter(all);

    return Scaffold(
      backgroundColor: AppColors.bgCanvas,
      body: SafeArea(
        bottom: false,
        child: RefreshIndicator(
          color: AppColors.primary,
          onRefresh: () => ref.read(patientsProvider.notifier).refresh(),
          child: CustomScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            slivers: <Widget>[
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.only(top: AppSpacing.xs),
                  child: TopBar(
                    title: 'Patients',
                    subtitle:
                        '${all.length} record${all.length == 1 ? '' : 's'} on this device',
                    leadingIcon: 'menu',
                    onLeadingTap: () => context.go('/home'),
                    trailing: <Widget>[
                      CircleIconButton(
                        icon: 'refreshCw',
                        tooltip: 'Refresh',
                        onTap: () =>
                            ref.read(patientsProvider.notifier).refresh(),
                      ),
                    ],
                  ),
                ),
              ),
              SliverToBoxAdapter(
                child: SectionReveal(
                  index: 1,
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(
                      AppSpacing.screenH,
                      AppSpacing.sm,
                      AppSpacing.screenH,
                      AppSpacing.md,
                    ),
                    child: SearchPill(
                      hint: 'Search by name or age',
                      onChanged: (String v) => setState(() => _query = v),
                    ),
                  ),
                ),
              ),
              if (slice.loading && !slice.hasData)
                const SliverToBoxAdapter(
                  child: Padding(
                    padding:
                        EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
                    child: Column(
                      children: <Widget>[
                        SkeletonRow(),
                        SizedBox(height: AppSpacing.xs),
                        SkeletonRow(),
                        SizedBox(height: AppSpacing.xs),
                        SkeletonRow(),
                      ],
                    ),
                  ),
                )
              else if (slice.hasError && all.isEmpty)
                SliverFillRemaining(
                  hasScrollBody: false,
                  child: ErrorStateView(
                    message: slice.error!.message,
                    onRetry: () =>
                        ref.read(patientsProvider.notifier).refresh(),
                  ),
                )
              else if (visible.isEmpty)
                SliverFillRemaining(
                  hasScrollBody: false,
                  child: EmptyState(
                    icon: 'users',
                    title: all.isEmpty ? 'No patients yet' : 'No matches',
                    message: all.isEmpty
                        ? 'Create a patient, then upload or scan their records to begin.'
                        : 'No patient matches “$_query”.',
                    actionLabel: all.isEmpty ? 'Add patient' : null,
                    onAction: all.isEmpty
                        ? () => showCreatePatientSheet(context, ref)
                        : null,
                  ),
                )
              else
                SliverList.separated(
                  itemCount: visible.length,
                  separatorBuilder: (_, __) =>
                      const SizedBox(height: AppSpacing.xs),
                  itemBuilder: (BuildContext context, int i) {
                    final Patient p = visible[i];
                    return SectionReveal(
                      index: i,
                      child: Padding(
                        padding: EdgeInsets.fromLTRB(
                          AppSpacing.screenH,
                          i == 0 ? 0 : 0,
                          AppSpacing.screenH,
                          0,
                        ),
                        child: PatientRow(
                          patient: p,
                          isActive: p.id == activeId,
                          onTap: () => openPatientOverview(
                              context, ref, p.id, p.fullName),
                        ),
                      ),
                    );
                  },
                ),
              SliverToBoxAdapter(
                child: SectionReveal(
                  index: visible.length,
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(
                      AppSpacing.screenH,
                      AppSpacing.md,
                      AppSpacing.screenH,
                      0,
                    ),
                    child: Center(
                      child: AddRow(
                        label: 'Add Patient',
                        onTap: () => showCreatePatientSheet(context, ref),
                      ),
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

  List<Patient> _filter(List<Patient> all) {
    final String q = _query.trim().toLowerCase();
    if (q.isEmpty) return all;
    return all
        .where((Patient p) =>
            p.fullName.toLowerCase().contains(q) ||
            p.ageLabel.toLowerCase().contains(q) ||
            p.sexLabel.toLowerCase().contains(q))
        .toList(growable: false);
  }
}

/// `LinkRowCard` with a monogram thumbnail and an `Active` marker.
class PatientRow extends StatelessWidget {
  const PatientRow({
    super.key,
    required this.patient,
    required this.onTap,
    this.isActive = false,
    this.onPin,
    this.ambientImage,
  });

  final Patient patient;
  final VoidCallback onTap;
  final bool isActive;
  final VoidCallback? onPin;
  final String? ambientImage;

  @override
  Widget build(BuildContext context) {
    return LinkRowCard(
      title: patient.fullName,
      label: patient.sexLabel,
      meta: '${patient.ageLabel} • ${patient.lastSeenLabel}',
      onTap: onTap,
      thumbnailAsset: ambientImage ?? kPatientAmbientImages.first,
      trailing: isActive
          ? const StatusPill(
              label: 'Active', variant: StatusPillVariant.approved, dense: true)
          : null,
    );
  }
}
