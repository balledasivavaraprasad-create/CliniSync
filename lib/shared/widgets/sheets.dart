import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/models/patient.dart';
import '../../core/repositories/providers.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_radii.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/utils/date_format.dart';
import '../../features/state/feature_providers.dart';
import '../cards/clin_cards.dart';
import '../loading/states.dart';
import '../navigation/route_names.dart';
import '../widgets/app_icons.dart';
import '../widgets/primitives.dart';

/// Grabber + title shown at the top of every ClinSync sheet.
class SheetScaffold extends StatelessWidget {
  const SheetScaffold({
    super.key,
    required this.title,
    required this.child,
    this.subtitle,
    this.footer,
  });

  final String title;
  final String? subtitle;
  final Widget child;
  final Widget? footer;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          const SizedBox(height: AppSpacing.sm),
          Container(
            width: 40,
            height: 4,
            decoration: const BoxDecoration(
              color: AppColors.dividerStrong,
              borderRadius: AppRadii.allPill,
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(
                AppSpacing.screenH, AppSpacing.md, AppSpacing.screenH, 0),
            child: Row(
              children: <Widget>[
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      Text(title, style: AppTypography.titleScreen),
                      if (subtitle != null) ...<Widget>[
                        const SizedBox(height: 1),
                        Text(subtitle!, style: AppTypography.titleScreenSub),
                      ],
                    ],
                  ),
                ),
                CircleIconButton(
                  icon: 'x',
                  size: 38,
                  iconSize: 17,
                  onTap: () => Navigator.of(context).maybePop(),
                ),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          Flexible(child: child),
          if (footer != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.screenH,
                AppSpacing.sm,
                AppSpacing.screenH,
                AppSpacing.md,
              ),
              child: footer!,
            ),
        ],
      ),
    );
  }
}

/// Shown on the `Records` and `Memory` tabs when no patient is selected
/// (plan §8 "if none selected, show a styled prompt to pick a patient").
class NoActivePatient extends ConsumerWidget {
  const NoActivePatient(
      {super.key, required this.title, required this.message});

  final String title;
  final String message;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Center(
      child: EmptyState(
        icon: 'users',
        title: title,
        message: message,
        actionLabel: 'Choose patient',
        onAction: () => showPatientPicker(context, ref),
      ),
    );
  }
}

/// Opens the patient picker sheet and selects the chosen patient.
Future<void> showPatientPicker(BuildContext context, WidgetRef ref) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: AppColors.bgCanvas,
    builder: (BuildContext sheetContext) => const _PatientPickerSheet(),
  );
}

class _PatientPickerSheet extends ConsumerStatefulWidget {
  const _PatientPickerSheet();

  @override
  ConsumerState<_PatientPickerSheet> createState() =>
      _PatientPickerSheetState();
}

class _PatientPickerSheetState extends ConsumerState<_PatientPickerSheet> {
  String _query = '';

  @override
  Widget build(BuildContext context) {
    final AsyncSlice<List<Patient>> slice = ref.watch(patientsProvider);
    final List<Patient> all = slice.data ?? const <Patient>[];
    final String q = _query.trim().toLowerCase();
    final List<Patient> filtered = q.isEmpty
        ? all
        : all
            .where((Patient p) => p.fullName.toLowerCase().contains(q))
            .toList(growable: false);

    return DraggableScrollableSheet(
      initialChildSize: 0.7,
      minChildSize: 0.4,
      maxChildSize: 0.92,
      expand: false,
      builder: (BuildContext context, ScrollController controller) {
        return SheetScaffold(
          title: 'Choose patient',
          subtitle: '${all.length} record${all.length == 1 ? '' : 's'}',
          child: Column(
            children: <Widget>[
              Padding(
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.screenH,
                  0,
                  AppSpacing.screenH,
                  AppSpacing.sm,
                ),
                child: SearchPill(
                  hint: 'Search patients',
                  onChanged: (String v) => setState(() => _query = v),
                  onMicTap: null,
                ),
              ),
              Expanded(
                child: slice.loading && all.isEmpty
                    ? const Center(
                        child: CircularProgressIndicator(strokeWidth: 2))
                    : filtered.isEmpty
                        ? const EmptyState(
                            icon: 'users',
                            title: 'No patients yet',
                            message:
                                'Create a patient to start collecting records.',
                            compact: true,
                          )
                        : ListView.separated(
                            controller: controller,
                            padding: const EdgeInsets.fromLTRB(
                              AppSpacing.screenH,
                              0,
                              AppSpacing.screenH,
                              AppSpacing.md,
                            ),
                            itemCount: filtered.length,
                            separatorBuilder: (_, __) =>
                                const SizedBox(height: AppSpacing.xs),
                            itemBuilder: (BuildContext context, int i) {
                              final Patient p = filtered[i];
                              return LinkRowCard(
                                title: p.fullName,
                                meta: '${p.ageLabel} • ${p.lastSeenLabel}',
                                thumbnailIcon: 'user',
                                onTap: () {
                                  ref
                                      .read(activePatientIdProvider.notifier)
                                      .select(p.id);
                                  Navigator.of(context).maybePop();
                                },
                              );
                            },
                          ),
              ),
            ],
          ),
        );
      },
    );
  }
}

/// "Create patient" form — `POST /api/v1/patients` (plan §9.2).
Future<bool?> showCreatePatientSheet(BuildContext context, WidgetRef ref) {
  return showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    backgroundColor: AppColors.bgCanvas,
    builder: (BuildContext sheetContext) => const _CreatePatientSheet(),
  );
}

class _CreatePatientSheet extends ConsumerStatefulWidget {
  const _CreatePatientSheet();

  @override
  ConsumerState<_CreatePatientSheet> createState() =>
      _CreatePatientSheetState();
}

class _CreatePatientSheetState extends ConsumerState<_CreatePatientSheet> {
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();
  final TextEditingController _name = TextEditingController();
  final TextEditingController _dob = TextEditingController();
  String _sex = '';
  bool _saving = false;
  bool _useAge = false;
  final TextEditingController _age = TextEditingController();

  @override
  void dispose() {
    _name.dispose();
    _dob.dispose();
    _age.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    setState(() => _saving = true);
    try {
      final Patient created = await ref.read(patientsProvider.notifier).create(
            fullName: _name.text.trim(),
            dateOfBirth: _useAge
                ? null
                : (_dob.text.trim().isEmpty ? null : _dob.text.trim()),
            ageYears: _useAge ? int.tryParse(_age.text.trim()) : null,
            sex: _sex.isEmpty ? null : _sex,
          );
      ref.read(activePatientIdProvider.notifier).select(created.id);
      if (mounted) {
        AppSnack.show(context, '${created.fullName} added');
        Navigator.of(context).pop(true);
      }
    } catch (e) {
      if (mounted) {
        setState(() => _saving = false);
        AppSnack.error(context, 'Could not add that patient. Try again.');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final double inset = MediaQuery.viewInsetsOf(context).bottom;
    return Padding(
      padding: EdgeInsets.only(bottom: inset),
      child: SheetScaffold(
        title: 'Add patient',
        subtitle: 'Fictional demo records only',
        footer: PrimaryPillButton(
          label: _saving ? 'Saving…' : 'Create patient',
          enabled: !_saving,
          onPressed: _submit,
        ),
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.screenH,
            0,
            AppSpacing.screenH,
            AppSpacing.md,
          ),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: <Widget>[
                TextFormField(
                  controller: _name,
                  textCapitalization: TextCapitalization.words,
                  decoration: const InputDecoration(labelText: 'Full name'),
                  validator: (String? v) => (v == null || v.trim().isEmpty)
                      ? 'Name is required'
                      : null,
                ),
                const SizedBox(height: AppSpacing.sm),
                SwitchListTile.adaptive(
                  contentPadding: EdgeInsets.zero,
                  value: _useAge,
                  activeThumbColor: AppColors.surface,
                  title: Text('Enter age instead of date of birth',
                      style: AppTypography.body),
                  onChanged: (bool v) => setState(() => _useAge = v),
                ),
                if (_useAge)
                  TextFormField(
                    controller: _age,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(labelText: 'Age (years)'),
                    validator: (String? v) {
                      if (v == null || v.trim().isEmpty) return null;
                      final int? n = int.tryParse(v.trim());
                      if (n == null || n < 0 || n > 130) return 'Enter 0–130';
                      return null;
                    },
                  )
                else
                  TextFormField(
                    controller: _dob,
                    decoration: const InputDecoration(
                      labelText: 'Date of birth (optional)',
                      hintText: '1984-03-22',
                    ),
                  ),
                const SizedBox(height: AppSpacing.sm),
                DropdownButtonFormField<String>(
                  initialValue: _sex.isEmpty ? null : _sex,
                  decoration:
                      const InputDecoration(labelText: 'Sex (optional)'),
                  items: const <DropdownMenuItem<String>>[
                    DropdownMenuItem<String>(
                        value: 'male', child: Text('Male')),
                    DropdownMenuItem<String>(
                        value: 'female', child: Text('Female')),
                    DropdownMenuItem<String>(
                        value: 'other', child: Text('Other')),
                  ],
                  onChanged: (String? v) => setState(() => _sex = v ?? ''),
                ),
                const SizedBox(height: AppSpacing.md),
                const ClinicalDisclaimer(
                  text:
                      'Use fictional records only. ClinSync is a prototype and does not store real patient data.',
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Guard used by quick actions: returns the active patient id, opening the
/// picker first when none is selected (plan §9.1).
Future<String?> requireActivePatient(
    BuildContext context, WidgetRef ref) async {
  final String? current = ref.read(activePatientIdProvider);
  if (current != null && current.isNotEmpty) return current;
  await showPatientPicker(context, ref);
  final String? picked = ref.read(activePatientIdProvider);
  if (picked == null && context.mounted) {
    AppSnack.error(context, 'Choose a patient first.');
  }
  return picked;
}

/// Convenience: push the Patient Overview for [patientId] and set it active.
void openPatientOverview(
    BuildContext context, WidgetRef ref, String patientId, String? name) {
  ref.read(activePatientIdProvider.notifier).select(patientId);
  context.push(
    '/patients/${Uri.encodeComponent(patientId)}',
    extra: OverviewArgs(patientId: patientId, patientName: name),
  );
}

/// Sub-line under a patient name: `52 yrs • Male • Last seen 28 Sep 2026`.
String patientMetaLine({
  required int? ageYears,
  required Object? dateOfBirth,
  required String? sex,
  required Object? lastActivityAt,
}) {
  final List<String> parts = <String>[
    AppDate.ageLabel(ageYears: ageYears, dateOfBirth: dateOfBirth),
    switch (sex?.toLowerCase()) {
      'male' || 'm' => 'Male',
      'female' || 'f' => 'Female',
      'other' || 'o' => 'Other',
      _ => 'Sex not recorded',
    },
    AppDate.relative(lastActivityAt),
  ];
  return parts.join(' • ');
}

/// Small icon used on sheet headers.
IconData sheetIcon(String name) => AppIcons.byName(name);
