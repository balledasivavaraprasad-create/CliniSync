import 'dart:async';
import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/animations/motion.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../features/state/feature_providers.dart';
import '../loading/states.dart';
import 'app_icons.dart';
import 'sheets.dart';

/// Plan §9.3: `+ Add Record` → this sheet (Upload / Camera / Voice).
Future<void> showRecordSourceSheet(
    BuildContext context, WidgetRef ref, String patientId) {
  return showModalBottomSheet<void>(
    context: context,
    backgroundColor: AppColors.bgCanvas,
    builder: (BuildContext sheetContext) =>
        _RecordSourceSheet(patientId: patientId),
  );
}

class _RecordSourceSheet extends ConsumerStatefulWidget {
  const _RecordSourceSheet({required this.patientId});

  final String patientId;

  @override
  ConsumerState<_RecordSourceSheet> createState() => _RecordSourceSheetState();
}

class _RecordSourceSheetState extends ConsumerState<_RecordSourceSheet> {
  bool _busy = false;

  Future<void> _upload() async {
    setState(() => _busy = true);
    try {
      final FilePickerResult? result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: <String>['pdf', 'jpg', 'jpeg', 'png', 'webp'],
        withData: false,
      );
      final String? path = result?.files.single.path;
      if (path == null) return;
      final doc =
          await ref.read(documentsProvider(widget.patientId).notifier).upload(
                File(path),
                uploadedVia: 'upload',
              );
      if (!mounted) return;
      AppSnack.show(context, '${doc.displayName} uploaded');
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

  @override
  Widget build(BuildContext context) {
    return SheetScaffold(
      title: 'Add a record',
      subtitle: 'Upload, scan or dictate',
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          _SourceOption(
            iconName: 'fileUp',
            title: 'Upload a file',
            subtitle: 'PDF, JPEG, PNG or WebP · up to 25 MB',
            busy: _busy,
            onTap: _upload,
          ),
          _SourceOption(
            iconName: 'camera',
            title: 'Scan with camera',
            subtitle: 'Capture a page and process it immediately',
            onTap: () {
              Navigator.of(context).pop();
              context.push('/camera/${widget.patientId}');
            },
          ),
          _SourceOption(
            iconName: 'mic',
            title: 'Dictate a voice note',
            subtitle: 'Transcribed, then linked to the patient as facts',
            onTap: () {
              Navigator.of(context).pop();
              context.push('/voice/${widget.patientId}');
            },
          ),
          const SizedBox(height: AppSpacing.sm),
          const ClinicalDisclaimer(),
        ],
      ),
    );
  }
}

class _SourceOption extends StatelessWidget {
  const _SourceOption({
    required this.iconName,
    required this.title,
    required this.subtitle,
    required this.onTap,
    this.busy = false,
  });

  final String iconName;
  final String title;
  final String subtitle;
  final VoidCallback onTap;
  final bool busy;

  @override
  Widget build(BuildContext context) {
    return PressScale(
      onTap: busy ? null : onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(
            vertical: AppSpacing.xs, horizontal: AppSpacing.xs),
        child: Row(
          children: <Widget>[
            Container(
              width: 44,
              height: 44,
              decoration: const BoxDecoration(
                  color: AppColors.surface, shape: BoxShape.circle),
              alignment: Alignment.center,
              child: Icon(AppIcons.byName(iconName),
                  size: 20, color: AppColors.primary),
            ),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  Text(title, style: AppTypography.bodyStrong),
                  Text(subtitle,
                      style: AppTypography.bodyBullet.copyWith(fontSize: 11.5)),
                ],
              ),
            ),
            if (busy)
              const SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            else
              Icon(AppIcons.byName('chevronRight'),
                  size: 18, color: AppColors.textTertiary),
          ],
        ),
      ),
    );
  }
}
