import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/animations/motion.dart';
import '../../core/repositories/providers.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_radii.dart';
import '../../core/theme/app_shadows.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final TextEditingController _emailController =
      TextEditingController(text: 'doctor@clinsync.health');
  final TextEditingController _passwordController =
      TextEditingController(text: 'demo1234');
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();

  bool _obscurePassword = true;
  bool _isLoading = false;
  String? _errorMessage;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  void _fillPreset(String email, String password) {
    setState(() {
      _emailController.text = email;
      _passwordController.text = password;
      _errorMessage = null;
    });
  }

  Future<void> _handleLogin() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final email = _emailController.text.trim();
      final password = _passwordController.text.trim();
      final authRepo = ref.read(authRepositoryProvider);
      final user = await authRepo.login(email, password);

      ref.read(currentUserProvider.notifier).setUser(user);

      if (mounted) {
        context.go('/home');
      }
    } catch (e) {
      setState(() {
        _errorMessage = e.toString().contains('Invalid')
            ? 'Invalid clinical credentials. Please verify your email and password.'
            : 'Authentication failed. Please check server connectivity.';
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bgCanvas,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.screenH,
              vertical: AppSpacing.xl,
            ),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 460),
              child: Form(
                key: _formKey,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: <Widget>[
                    // ── Header & Brand Mark ───────────────────────────────
                    Center(
                      child: Container(
                        width: 60,
                        height: 60,
                        decoration: BoxDecoration(
                          color: AppColors.primarySoft,
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: AppColors.primary.withValues(alpha: 0.3),
                            width: 2,
                          ),
                          boxShadow: AppShadows.card,
                        ),
                        child: const Icon(
                          LucideIcons.activity,
                          color: AppColors.primary,
                          size: 30,
                        ),
                      ),
                    ),
                    const SizedBox(height: AppSpacing.md),
                    Text(
                      'ClinSync',
                      textAlign: TextAlign.center,
                      style: AppTypography.displayHero.copyWith(
                        fontSize: 34,
                        color: AppColors.primaryDark,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.xxs),
                    Text(
                      'Longitudinal Clinical Intelligence & Doctor Preparation',
                      textAlign: TextAlign.center,
                      style: AppTypography.caption.copyWith(
                        color: AppColors.textSecondary,
                        fontSize: 13,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.lg),

                    // ── Card container ───────────────────────────────────
                    Container(
                      padding: const EdgeInsets.all(AppSpacing.lg),
                      decoration: BoxDecoration(
                        color: AppColors.surface,
                        borderRadius: AppRadii.allMd,
                        border: Border.all(color: AppColors.divider),
                        boxShadow: AppShadows.card,
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: <Widget>[
                          Row(
                            children: <Widget>[
                              const Icon(
                                LucideIcons.shieldCheck,
                                color: AppColors.primary,
                                size: 18,
                              ),
                              const SizedBox(width: AppSpacing.xs),
                              Text(
                                'Clinician Sign In',
                                style: AppTypography.titleSection,
                              ),
                              const Spacer(),
                              Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 8,
                                  vertical: 3,
                                ),
                                decoration: const BoxDecoration(
                                  color: AppColors.surfaceTint,
                                  borderRadius: AppRadii.allPill,
                                ),
                                child: Text(
                                  'Live Database',
                                  style: AppTypography.caption.copyWith(
                                    color: AppColors.primaryMuted,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: AppSpacing.md),

                          // Error alert banner
                          if (_errorMessage != null) ...<Widget>[
                            Container(
                              padding: const EdgeInsets.all(AppSpacing.sm),
                              decoration: BoxDecoration(
                                color: AppColors.dangerSoft,
                                borderRadius: AppRadii.allSm,
                                border: Border.all(
                                  color: AppColors.danger.withValues(alpha: 0.4),
                                ),
                              ),
                              child: Row(
                                children: <Widget>[
                                  const Icon(
                                    LucideIcons.alertCircle,
                                    color: AppColors.danger,
                                    size: 18,
                                  ),
                                  const SizedBox(width: AppSpacing.xs),
                                  Expanded(
                                    child: Text(
                                      _errorMessage!,
                                      style: AppTypography.body.copyWith(
                                        color: AppColors.danger,
                                        fontWeight: FontWeight.w500,
                                        fontSize: 13,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(height: AppSpacing.md),
                          ],

                          // Email field
                          Text('Clinical Email', style: AppTypography.label),
                          const SizedBox(height: 6),
                          TextFormField(
                            controller: _emailController,
                            keyboardType: TextInputType.emailAddress,
                            autocorrect: false,
                            style: AppTypography.body,
                            decoration: const InputDecoration(
                              hintText: 'name@clinsync.health',
                              prefixIcon: Icon(
                                LucideIcons.mail,
                                size: 18,
                                color: AppColors.textSecondary,
                              ),
                              filled: true,
                              fillColor: AppColors.surfaceTint,
                              contentPadding: EdgeInsets.symmetric(
                                horizontal: AppSpacing.md,
                                vertical: 14,
                              ),
                              border: OutlineInputBorder(
                                borderRadius: AppRadii.allSm,
                                borderSide: BorderSide(color: AppColors.divider),
                              ),
                              enabledBorder: OutlineInputBorder(
                                borderRadius: AppRadii.allSm,
                                borderSide: BorderSide(color: AppColors.divider),
                              ),
                              focusedBorder: OutlineInputBorder(
                                borderRadius: AppRadii.allSm,
                                borderSide: BorderSide(
                                  color: AppColors.primary,
                                  width: 1.5,
                                ),
                              ),
                            ),
                            validator: (v) {
                              if (v == null || v.trim().isEmpty) {
                                return 'Email is required';
                              }
                              return null;
                            },
                          ),
                          const SizedBox(height: AppSpacing.md),

                          // Password field
                          Text('Password', style: AppTypography.label),
                          const SizedBox(height: 6),
                          TextFormField(
                            controller: _passwordController,
                            obscureText: _obscurePassword,
                            style: AppTypography.body,
                            decoration: InputDecoration(
                              hintText: 'Enter password',
                              prefixIcon: const Icon(
                                LucideIcons.lock,
                                size: 18,
                                color: AppColors.textSecondary,
                              ),
                              suffixIcon: IconButton(
                                icon: Icon(
                                  _obscurePassword
                                      ? LucideIcons.eye
                                      : LucideIcons.eyeOff,
                                  size: 18,
                                  color: AppColors.textSecondary,
                                ),
                                onPressed: () {
                                  setState(() {
                                    _obscurePassword = !_obscurePassword;
                                  });
                                },
                              ),
                              filled: true,
                              fillColor: AppColors.surfaceTint,
                              contentPadding: const EdgeInsets.symmetric(
                                horizontal: AppSpacing.md,
                                vertical: 14,
                              ),
                              border: const OutlineInputBorder(
                                borderRadius: AppRadii.allSm,
                                borderSide: BorderSide(color: AppColors.divider),
                              ),
                              enabledBorder: const OutlineInputBorder(
                                borderRadius: AppRadii.allSm,
                                borderSide: BorderSide(color: AppColors.divider),
                              ),
                              focusedBorder: const OutlineInputBorder(
                                borderRadius: AppRadii.allSm,
                                borderSide: BorderSide(
                                  color: AppColors.primary,
                                  width: 1.5,
                                ),
                              ),
                            ),
                            validator: (v) {
                              if (v == null || v.trim().isEmpty) {
                                return 'Password is required';
                              }
                              return null;
                            },
                          ),
                          const SizedBox(height: AppSpacing.lg),

                          // Sign In CTA
                          PressScale(
                            onTap: _isLoading ? null : _handleLogin,
                            child: Container(
                              height: 48,
                              decoration: BoxDecoration(
                                color: _isLoading
                                    ? AppColors.primary.withValues(alpha: 0.7)
                                    : AppColors.primary,
                                borderRadius: AppRadii.allPill,
                                boxShadow: _isLoading ? null : AppShadows.button,
                              ),
                              alignment: Alignment.center,
                              child: _isLoading
                                  ? const SizedBox(
                                      width: 22,
                                      height: 22,
                                      child: CircularProgressIndicator(
                                        strokeWidth: 2.2,
                                        color: Colors.white,
                                      ),
                                    )
                                  : Row(
                                      mainAxisAlignment: MainAxisAlignment.center,
                                      children: <Widget>[
                                        const Icon(
                                          LucideIcons.logIn,
                                          size: 18,
                                          color: AppColors.onPrimary,
                                        ),
                                        const SizedBox(width: AppSpacing.xs),
                                        Text(
                                          'Sign in to ClinSync',
                                          style: AppTypography.button,
                                        ),
                                      ],
                                    ),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: AppSpacing.md),

                    // ── Preset Demo Clinicians ──────────────────────────
                    Container(
                      padding: const EdgeInsets.all(AppSpacing.md),
                      decoration: BoxDecoration(
                        color: AppColors.surfaceTint,
                        borderRadius: AppRadii.allSm,
                        border: Border.all(
                          color: AppColors.primarySoft.withValues(alpha: 0.8),
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Row(
                            children: <Widget>[
                              const Icon(
                                LucideIcons.userCheck,
                                size: 15,
                                color: AppColors.primary,
                              ),
                              const SizedBox(width: 6),
                              Text(
                                'Quick Fill Demo Clinicians:',
                                style: AppTypography.caption.copyWith(
                                  color: AppColors.textPrimary,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: AppSpacing.xs),
                          Wrap(
                            spacing: 8,
                            runSpacing: 6,
                            children: <Widget>[
                              _PresetChip(
                                label: 'Dr. Willie Carter (General)',
                                active: _emailController.text ==
                                    'doctor@clinsync.health',
                                onTap: () => _fillPreset(
                                  'doctor@clinsync.health',
                                  'demo1234',
                                ),
                              ),
                              _PresetChip(
                                label: 'Dr. Sarah Jenkins (Cardio)',
                                active: _emailController.text ==
                                    'sarah.jenkins@clinsync.health',
                                onTap: () => _fillPreset(
                                  'sarah.jenkins@clinsync.health',
                                  'demo1234',
                                ),
                              ),
                              _PresetChip(
                                label: 'Dr. Alex Mercer (Internal)',
                                active:
                                    _emailController.text == 'demo@clinsync.health',
                                onTap: () => _fillPreset(
                                  'demo@clinsync.health',
                                  'demo1234',
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: AppSpacing.lg),

                    // Security assurance footer
                    Center(
                      child: Text(
                        'Encrypted clinical session · HIPAA aligned · Multi-device enabled',
                        style: AppTypography.caption.copyWith(
                          color: AppColors.textTertiary,
                          fontSize: 11,
                        ),
                        textAlign: TextAlign.center,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _PresetChip extends StatelessWidget {
  const _PresetChip({
    required this.label,
    required this.active,
    required this.onTap,
  });

  final String label;
  final bool active;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: AppRadii.allPill,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: active ? AppColors.primarySoft : AppColors.surface,
          borderRadius: AppRadii.allPill,
          border: Border.all(
            color: active ? AppColors.primary : AppColors.divider,
            width: active ? 1.4 : 1,
          ),
        ),
        child: Text(
          label,
          style: AppTypography.caption.copyWith(
            color: active ? AppColors.primaryDark : AppColors.textSecondary,
            fontWeight: active ? FontWeight.w700 : FontWeight.w500,
          ),
        ),
      ),
    );
  }
}
