import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/animations/motion.dart';
import '../../core/config/app_config.dart';
import '../../core/constants/enums.dart';
import '../../core/models/specialty.dart';
import '../../core/repositories/providers.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_radii.dart';
import '../../core/theme/app_shadows.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../features/state/feature_providers.dart';
import '../loading/states.dart';
import '../widgets/app_icons.dart';
import '../widgets/primitives.dart';
import 'sheets.dart';

/// Home menu sheet — plan §9.1: API base URL, Demo mode toggle, about /
/// disclaimer, and clinician session details.
Future<void> showSettingsSheet(BuildContext context, WidgetRef ref) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: AppColors.bgCanvas,
    builder: (BuildContext sheetContext) => const _SettingsSheet(),
  );
}

class _SettingsSheet extends ConsumerStatefulWidget {
  const _SettingsSheet();

  @override
  ConsumerState<_SettingsSheet> createState() => _SettingsSheetState();
}

class _SettingsSheetState extends ConsumerState<_SettingsSheet> {
  late final TextEditingController _url = TextEditingController(
    text: AppConfig.origin,
  );
  String? _error;

  @override
  void dispose() {
    _url.dispose();
    super.dispose();
  }

  Future<void> _applyUrl(String raw) async {
    final String normalised = AppConfig.withScheme(raw);
    if (normalised.isEmpty) {
      setState(() => _error = 'Enter a host or URL');
      return;
    }
    final Uri? parsed = Uri.tryParse(normalised);
    if (parsed == null || !parsed.hasScheme || parsed.host.isEmpty) {
      setState(() => _error = 'That does not look like a valid URL');
      return;
    }
    setState(() => _error = null);
    await ref.read(appSettingsProvider.notifier).setBaseUrl(normalised);
    _url.text = AppConfig.origin;
    if (mounted) {
      AppSnack.show(context, 'Server set to ${AppConfig.origin}');
      ref.invalidate(healthProvider);
    }
  }

  @override
  Widget build(BuildContext context) {
    final AppSettings settings = ref.watch(appSettingsProvider);
    final bool healthy = ref.watch(healthProvider).maybeWhen(
          data: (bool v) => v,
          orElse: () => false,
        );
    final Specialty specialty = ref.watch(specialtyProvider);
    final List<SpecialtyOption> catalog =
        ref.watch(specialtyCatalogProvider).value ??
            SpecialtyOption.mirroringBackend();

    final user = ref.watch(currentUserProvider);

    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: SheetScaffold(
        title: 'ClinSync settings',
        subtitle: user != null
            ? '${user.fullName} · ${user.specialty}'
            : 'Clinical workstation configuration',
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.screenH,
            0,
            AppSpacing.screenH,
            AppSpacing.md,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              // ── Clinician Profile & Session
              SurfaceCard(
                padding: const EdgeInsets.all(AppSpacing.sm),
                child: Row(
                  children: <Widget>[
                    Container(
                      width: 42,
                      height: 42,
                      decoration: BoxDecoration(
                        color: AppColors.primarySoft,
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: AppColors.primary.withValues(alpha: 0.2),
                        ),
                      ),
                      alignment: Alignment.center,
                      child: const Icon(
                        LucideIcons.stethoscope,
                        color: AppColors.primaryDark,
                        size: 20,
                      ),
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Text(
                            user?.fullName ?? 'Dr. Willie Carter, MD',
                            style: AppTypography.titleCard.copyWith(
                              fontSize: 15,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          Text(
                            '${user?.email ?? "doctor@clinsync.health"} · ${user?.specialty ?? "General Medicine"}',
                            style: AppTypography.caption.copyWith(
                              color: AppColors.textSecondary,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ),
                    ),
                    TextButton.icon(
                      style: TextButton.styleFrom(
                        foregroundColor: AppColors.danger,
                        padding: const EdgeInsets.symmetric(horizontal: 8),
                      ),
                      icon: const Icon(LucideIcons.logOut, size: 16),
                      label: const Text('Sign out'),
                      onPressed: () async {
                        await ref.read(currentUserProvider.notifier).logout();
                        if (context.mounted) {
                          Navigator.of(context).pop();
                          context.go('/login');
                        }
                      },
                    ),
                  ],
                ),
              ),
              const SizedBox(height: AppSpacing.md),

              // ── Connection
              Row(
                children: <Widget>[
                  Text('Server', style: AppTypography.titleSection),
                  const Spacer(),
                  StatusPill(
                    label: healthy ? 'Connected' : 'Unreachable',
                    variant: healthy
                        ? StatusPillVariant.approved
                        : StatusPillVariant.needsReview,
                    icon: healthy ? 'checkCircle' : 'alertTriangle',
                    dense: true,
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.xs),
              TextField(
                controller: _url,
                keyboardType: TextInputType.url,
                autocorrect: false,
                decoration: InputDecoration(
                  labelText: 'API base URL',
                  helperText:
                      'Run: uvicorn app.main:app --app-dir backend --port 8000',
                  errorText: _error,
                ),
                onSubmitted: _applyUrl,
              ),
              const SizedBox(height: AppSpacing.xs),
              Wrap(
                spacing: AppSpacing.xs,
                runSpacing: AppSpacing.xs,
                children: <Widget>[
                  for (final ({String label, String value}) hint
                      in AppConfig.baseUrlHints)
                    PressScale(
                      onTap: () => _applyUrl(hint.value),
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 6),
                        decoration: const BoxDecoration(
                          color: AppColors.surfaceTint,
                          borderRadius: AppRadii.allPill,
                        ),
                        child: Text(hint.label, style: AppTypography.caption),
                      ),
                    ),
                ],
              ),
              const SizedBox(height: AppSpacing.sm),
              PrimaryPillButton(
                label: 'Save server',
                icon: 'check',
                height: 48,
                onPressed: () => _applyUrl(_url.text),
              ),

              const SizedBox(height: AppSpacing.xl),

              // ── Demo mode
              Text('Offline data', style: AppTypography.titleSection),
              const SizedBox(height: AppSpacing.xs),
              SurfaceCard(
                padding: const EdgeInsets.all(AppSpacing.md),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Row(
                      children: <Widget>[
                        Icon(AppIcons.byName('database'),
                            size: 18, color: AppColors.primary),
                        const SizedBox(width: AppSpacing.xs),
                        Expanded(
                          child: Text('Demo mode',
                              style: AppTypography.bodyStrong),
                        ),
                        Switch.adaptive(
                          value: settings.demoMode,
                          activeThumbColor: AppColors.surface,
                          onChanged: (bool v) {
                            ref
                                .read(appSettingsProvider.notifier)
                                .setDemoMode(v);
                            ref.invalidate(healthProvider);
                          },
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      settings.demoMode
                          ? 'If the server is unreachable, bundled fictional records are shown and tagged “Demo data”.'
                          : 'If the server is unreachable, screens show a retry state instead of bundled data.',
                      style: AppTypography.bodyBullet,
                    ),
                  ],
                ),
              ),

              const SizedBox(height: AppSpacing.xl),

              // ── Specialty — labels come from `GET /specialties`, with the
              //    bundled mirror as the offline fallback.
              Text('Default specialty', style: AppTypography.titleSection),
              const SizedBox(height: AppSpacing.xs),
              Wrap(
                spacing: AppSpacing.xs,
                runSpacing: AppSpacing.xs,
                children: <Widget>[
                  for (final SpecialtyOption s in catalog)
                    PressScale(
                      onTap: () => ref
                          .read(specialtyProvider.notifier)
                          .select(s.specialty ?? Specialty.fromWire(s.id)),
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 12, vertical: 8),
                        decoration: BoxDecoration(
                          color: s.specialty == specialty
                              ? AppColors.primary
                              : AppColors.surface,
                          borderRadius: AppRadii.allPill,
                          boxShadow:
                              s.specialty == specialty ? null : AppShadows.card,
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: <Widget>[
                            Icon(
                              AppIcons.byName(s.icon),
                              size: 14,
                              color: s.specialty == specialty
                                  ? AppColors.onPrimary
                                  : AppColors.textSecondary,
                            ),
                            const SizedBox(width: 5),
                            Text(
                              s.name,
                              style: AppTypography.bodyBullet.copyWith(
                                color: s.specialty == specialty
                                    ? AppColors.onPrimary
                                    : AppColors.textPrimary,
                                fontSize: 12,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                ],
              ),

              const SizedBox(height: AppSpacing.xl),

              // ── About
              Text('About', style: AppTypography.titleSection),
              const SizedBox(height: AppSpacing.xs),
              SurfaceCard(
                padding: const EdgeInsets.all(AppSpacing.md),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Row(
                      children: <Widget>[
                        Container(
                          width: 40,
                          height: 40,
                          decoration: const BoxDecoration(
                            color: AppColors.primarySoft,
                            shape: BoxShape.circle,
                          ),
                          alignment: Alignment.center,
                          child: Text(
                            'C',
                            style: AppTypography.titleScreen.copyWith(
                              color: AppColors.primaryDark,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                        const SizedBox(width: AppSpacing.sm),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            mainAxisSize: MainAxisSize.min,
                            children: <Widget>[
                              Text('ClinSync', style: AppTypography.titleCard),
                              Text(
                                'AI-assisted pre-consultation intelligence',
                                style: AppTypography.caption,
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    const ClinicalDisclaimer(),
                    Text(
                      'Conflicts are surfaced side by side and never resolved automatically. '
                      'Confidence and provenance are always visible, and nothing becomes verified '
                      'until you approve it.',
                      style: AppTypography.bodyBullet,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              Center(
                child: TextButton(
                  onPressed: () => context.go('/galleries'),
                  child:
                      Text('Design system gallery', style: AppTypography.link),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
