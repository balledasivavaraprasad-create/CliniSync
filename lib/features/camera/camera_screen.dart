import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:permission_handler/permission_handler.dart';

import '../../core/animations/motion.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_radii.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../shared/loading/states.dart';
import '../../shared/widgets/app_icons.dart';
import '../../shared/widgets/primitives.dart';
import '../state/feature_providers.dart';

/// Camera / scan — plan §9.19.
///
/// Full-screen preview with translucent white circular controls, a large white
/// shutter with a green ring, a gallery shortcut, then a preview with `Retake`
/// and `Use Image`. `uploaded_via=camera` routes the file to `images/`.
class CameraScreen extends ConsumerStatefulWidget {
  const CameraScreen({super.key, required this.patientId});

  final String patientId;

  @override
  ConsumerState<CameraScreen> createState() => _CameraScreenState();
}

class _CameraScreenState extends ConsumerState<CameraScreen> {
  final ImagePicker _picker = ImagePicker();
  XFile? _captured;
  bool _busy = false;
  bool _permissionDenied = false;

  Future<void> _ensurePermission() async {
    final PermissionStatus status = await Permission.camera.request();
    if (status.isGranted || status.isLimited) return;
    if (!mounted) return;
    setState(() => _permissionDenied = true);
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _ensurePermission());
  }

  @override
  Widget build(BuildContext context) {
    if (_permissionDenied) return _PermissionDenied(onRetry: _ensurePermission);
    final XFile? shot = _captured;
    if (shot != null) {
      return _Preview(captured: shot, onUse: _use, onRetake: _retake);
    }
    return _CaptureSurface(
      onCapture: _capture,
      onGallery: _pickGallery,
      busy: _busy,
    );
  }

  Future<void> _capture() async {
    setState(() => _busy = true);
    try {
      final XFile? shot = await _picker.pickImage(
        source: ImageSource.camera,
        imageQuality: 88,
        maxWidth: 2400,
      );
      if (shot != null && mounted) setState(() => _captured = shot);
    } catch (_) {
      if (mounted) {
        AppSnack.error(
            context, 'The camera could not be opened on this device.');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _pickGallery() async {
    setState(() => _busy = true);
    try {
      final XFile? shot = await _picker.pickImage(
          source: ImageSource.gallery, imageQuality: 90);
      if (shot != null && mounted) setState(() => _captured = shot);
    } catch (_) {
      if (mounted) AppSnack.error(context, 'That image could not be opened.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _retake() => setState(() => _captured = null);

  Future<void> _use() async {
    final XFile? shot = _captured;
    if (shot == null) return;
    setState(() => _busy = true);
    try {
      final doc =
          await ref.read(documentsProvider(widget.patientId).notifier).upload(
                File(shot.path),
                uploadedVia: 'camera',
              );
      if (!mounted) return;
      AppSnack.show(context, 'Scan uploaded');
      await context.push(
        '/documents/${Uri.encodeComponent(doc.id)}/processing'
        '?patient=${widget.patientId}&name=${Uri.encodeQueryComponent(doc.displayName)}',
      );
    } catch (_) {
      if (mounted) {
        AppSnack.error(context, 'That upload did not complete. Try again.');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }
}

class _CaptureSurface extends StatelessWidget {
  const _CaptureSurface(
      {required this.onCapture, required this.onGallery, required this.busy});

  final VoidCallback onCapture;
  final VoidCallback onGallery;
  final bool busy;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF12160F),
      body: SafeArea(
        child: Stack(
          children: <Widget>[
            // Viewfinder framing — the preview itself is provided by the platform
            // picker; this is the framing chrome around it.
            Center(
              child: AspectRatio(
                aspectRatio: 3 / 4,
                child: Container(
                  decoration: BoxDecoration(
                    border: Border.all(
                      color: AppColors.onPrimary.withValues(alpha: 0.35),
                      width: 1.4,
                    ),
                    borderRadius: AppRadii.allLg,
                  ),
                ),
              ),
            ),
            Positioned(
              top: AppSpacing.md,
              left: AppSpacing.md,
              right: AppSpacing.md,
              child: Row(
                children: <Widget>[
                  _GlassButton(icon: 'x', onTap: () => context.pop()),
                  const Spacer(),
                  _GlassButton(
                    icon: 'zap',
                    tooltip: 'Flash is controlled by the device',
                    onTap: () => AppSnack.show(context,
                        'Flash is controlled by your device camera app.'),
                  ),
                ],
              ),
            ),
            Positioned(
              left: 0,
              right: 0,
              bottom: AppSpacing.xl,
              child: Column(
                children: <Widget>[
                  Text(
                    'Fill the frame with one record page',
                    style: AppTypography.body.copyWith(
                        color: AppColors.onPrimary.withValues(alpha: 0.8)),
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: <Widget>[
                      _ShutterSide(onTap: onGallery, icon: 'image'),
                      const SizedBox(width: AppSpacing.xxl),
                      _ShutterButton(
                          onTap: busy ? null : onCapture, busy: busy),
                      const SizedBox(width: AppSpacing.xxl),
                      const SizedBox(width: 56),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ShutterSide extends StatelessWidget {
  const _ShutterSide({required this.onTap, required this.icon});

  final VoidCallback onTap;
  final String icon;

  @override
  Widget build(BuildContext context) {
    return PressScale(
      onTap: onTap,
      child: Container(
        width: 56,
        height: 56,
        decoration: BoxDecoration(
          color: AppColors.onPrimary.withValues(alpha: 0.16),
          shape: BoxShape.circle,
        ),
        alignment: Alignment.center,
        child:
            Icon(AppIcons.byName(icon), size: 22, color: AppColors.onPrimary),
      ),
    );
  }
}

class _ShutterButton extends StatelessWidget {
  const _ShutterButton({required this.onTap, required this.busy});

  final VoidCallback? onTap;
  final bool busy;

  @override
  Widget build(BuildContext context) {
    return PressScale(
      onTap: onTap,
      child: Container(
        width: 76,
        height: 76,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          border: Border.all(color: AppColors.primary, width: 4),
        ),
        padding: const EdgeInsets.all(5),
        child: Container(
          decoration: BoxDecoration(
            color: AppColors.onPrimary,
            shape: BoxShape.circle,
            border: Border.all(
                color: AppColors.onPrimary.withValues(alpha: 0.4), width: 1),
          ),
          alignment: Alignment.center,
          child: busy
              ? const SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(
                      strokeWidth: 2, color: AppColors.primary),
                )
              : null,
        ),
      ),
    );
  }
}

class _GlassButton extends StatelessWidget {
  const _GlassButton({required this.icon, required this.onTap, this.tooltip});

  final String icon;
  final VoidCallback onTap;
  final String? tooltip;

  @override
  Widget build(BuildContext context) {
    Widget button = CircleIconButton(
      iconData: AppIcons.byName(icon),
      size: 44,
      iconSize: 20,
      color: AppColors.onPrimary,
      background: AppColors.onPrimary.withValues(alpha: 0.16),
      onTap: onTap,
    );
    if (tooltip != null) button = Tooltip(message: tooltip!, child: button);
    return button;
  }
}

class _Preview extends StatelessWidget {
  const _Preview(
      {required this.captured, required this.onUse, required this.onRetake});

  final XFile captured;
  final VoidCallback onUse;
  final VoidCallback onRetake;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bgCanvas,
      body: SafeArea(
        child: Column(
          children: <Widget>[
            TopBar(
              title: 'Review scan',
              subtitle: 'Check the page is readable',
              onLeadingTap: onRetake,
              leadingIcon: 'x',
            ),
            Expanded(
              child: Padding(
                padding:
                    const EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
                child: ClipRRect(
                  borderRadius: AppRadii.allLg,
                  child: Image.file(File(captured.path), fit: BoxFit.contain),
                ),
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            const ClinicalDisclaimer(
              text:
                  'A clearer scan produces higher extraction confidence. Nothing is read until you use the image.',
            ),
            SizedBox(
              height: 100,
              child: Row(
                children: <Widget>[
                  const SizedBox(width: AppSpacing.screenH),
                  Expanded(
                    child: PrimaryPillButton(
                      label: 'Retake',
                      height: 52,
                      onPressed: onRetake,
                      enabled: true,
                      icon: 'refreshCw',
                    ),
                  ),
                  const SizedBox(width: AppSpacing.xs),
                  Expanded(
                    child: PrimaryPillButton(
                      label: 'Use Image',
                      height: 52,
                      onPressed: onUse,
                      icon: 'check',
                    ),
                  ),
                  const SizedBox(width: AppSpacing.screenH),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PermissionDenied extends StatelessWidget {
  const _PermissionDenied({required this.onRetry});

  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bgCanvas,
      body: SafeArea(
        child: Column(
          children: <Widget>[
            TopBar(title: 'Camera', onLeadingTap: () => context.pop()),
            Expanded(
              child: ErrorStateView(
                title: 'Camera access is off',
                message:
                    'Allow camera access to scan a record, or upload a file instead.',
                retryLabel: 'Try again',
                onRetry: onRetry,
              ),
            ),
            const Padding(
              padding: EdgeInsets.all(AppSpacing.screenH),
              child: PrimaryPillButton(
                label: 'Open settings',
                icon: 'settings',
                onPressed: openAppSettings,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
