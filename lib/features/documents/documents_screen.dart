import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/animations/motion.dart';
import '../../core/constants/enums.dart';
import '../../core/models/document.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_radii.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/utils/confidence_band.dart';
import '../../core/utils/date_format.dart';
import '../../shared/loading/states.dart';
import '../../shared/widgets/app_icons.dart';
import '../../shared/widgets/primitives.dart';
import '../../shared/widgets/record_source_sheet.dart';
import '../state/feature_providers.dart';

/// The `PillTabs` filter — plan §9.4 `All · Prescription · Lab · Notes · Other`.
const List<String> kDocumentFilterLabels = <String>[
  'All',
  'Prescription',
  'Lab',
  'Notes',
  'Other',
];

RecordType? documentFilterFor(int index) => switch (index) {
      0 => null,
      1 => RecordType.prescription,
      2 => RecordType.labReport,
      3 => RecordType.consultationNote,
      _ => null,
    };

/// Documents & upload — plan §9.4, template: reference screen 2 cards.
class DocumentsScreen extends ConsumerStatefulWidget {
  const DocumentsScreen(
      {super.key, required this.patientId, this.embedded = false});

  final String patientId;
  final bool embedded;

  @override
  ConsumerState<DocumentsScreen> createState() => _DocumentsScreenState();
}

class _DocumentsScreenState extends ConsumerState<DocumentsScreen> {
  int _filter = 0;
  String? _uploadingFor;

  String get _id => widget.patientId;

  @override
  Widget build(BuildContext context) {
    final AsyncSlice<List<ClinicalDocument>> slice =
        ref.watch(documentsProvider(_id));
    final DocumentsNotifier notifier =
        ref.read(documentsProvider(_id).notifier);
    final List<ClinicalDocument> all = slice.data ?? const <ClinicalDocument>[];

    // The backend has more record types than the reference's four tabs, so the
    // remainder is folded into `Other`.
    final RecordType? filter = documentFilterFor(_filter);
    final List<ClinicalDocument> visible = switch (filter) {
      null when _filter == 0 => all,
      null => all
          .where((ClinicalDocument d) =>
              d.documentType != RecordType.prescription &&
              d.documentType != RecordType.labReport &&
              d.documentType != RecordType.consultationNote)
          .toList(growable: false),
      final RecordType t => all
          .where((ClinicalDocument d) => d.documentType == t)
          .toList(growable: false),
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
                title: 'Records',
                subtitle: widget.embedded
                    ? 'Evidence library'
                    : '${all.length} uploaded',
                showLeading: !widget.embedded,
                leadingIcon: 'arrowLeft',
                onLeadingTap: () => context.pop(),
                trailing: <Widget>[
                  CircleIconButton(
                    icon: 'refreshCw',
                    tooltip: 'Refresh',
                    onTap: notifier.refresh,
                  ),
                ],
              ),
              SectionReveal(
                index: 0,
                child: Padding(
                  padding: const EdgeInsets.only(
                      top: AppSpacing.sm, bottom: AppSpacing.sm),
                  child: PillTabs(
                    labels: kDocumentFilterLabels,
                    selectedIndex: _filter,
                    onChanged: (int i) => setState(() => _filter = i),
                  ),
                ),
              ),
              if (_uploadingFor != null)
                Padding(
                  padding: const EdgeInsets.fromLTRB(
                    AppSpacing.screenH,
                    0,
                    AppSpacing.screenH,
                    AppSpacing.sm,
                  ),
                  child: ClinNoticeBanner(
                    message: 'Uploading $_uploadingFor…',
                    icon: 'loader',
                    tone: ClinNoticeTone.primary,
                  ),
                ),
              if (slice.loading && !slice.hasData)
                const Padding(
                  padding: EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
                  child: Column(
                    children: <Widget>[
                      SkeletonRow(),
                      SizedBox(height: AppSpacing.xs),
                      SkeletonRow(),
                      SizedBox(height: AppSpacing.xs),
                      SkeletonRow(),
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
                  icon: 'files',
                  title:
                      all.isEmpty ? 'No records yet' : 'Nothing in this filter',
                  message: all.isEmpty
                      ? 'Upload a PDF or scan a document — ClinSync reads it and links every claim back to its source.'
                      : 'Choose “All” to see every uploaded record.',
                  actionLabel: all.isEmpty ? 'Upload a record' : null,
                  onAction: all.isEmpty
                      ? () => showRecordSourceSheet(context, ref, _id)
                      : null,
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
                            child: DocumentCard(
                              document: visible[i],
                              onTap: () => context.push(
                                '/documents/${Uri.encodeComponent(visible[i].id)}/processing'
                                '?patient=$_id&name=${Uri.encodeQueryComponent(visible[i].displayName)}',
                              ),
                              onProcess: visible[i].canProcess
                                  ? () => _process(notifier, visible[i])
                                  : null,
                            ),
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

      // ── StickyActionBar: Upload + circular Camera + circular Voice
      bottomNavigationBar: StickyActionBar(
        primaryLabel: 'Upload',
        primaryIcon: 'fileUp',
        enabled: _uploadingFor == null,
        onPrimary: () => _pickFile(notifier),
        extraSecondaryIcons: <Widget>[
          const SizedBox(width: AppSpacing.xs),
          CircleIconButton(
            icon: 'camera',
            tooltip: 'Scan document',
            size: 56,
            iconSize: 22,
            onTap: () => context.push('/camera/$_id'),
          ),
          const SizedBox(width: AppSpacing.xs),
          CircleIconButton(
            icon: 'mic',
            tooltip: 'Voice note',
            size: 56,
            iconSize: 22,
            onTap: () => context.push('/voice/$_id'),
          ),
        ],
      ),
    );
  }

  Future<void> _process(
      DocumentsNotifier notifier, ClinicalDocument doc) async {
    try {
      await notifier.process(doc);
      if (mounted) {
        AppSnack.show(context, 'Processing started for ${doc.displayName}');
      }
    } catch (_) {
      if (mounted) AppSnack.error(context, 'Could not start processing.');
    }
  }

  Future<void> _pickFile(DocumentsNotifier notifier) async {
    try {
      final FilePickerResult? result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: <String>['pdf', 'jpg', 'jpeg', 'png', 'webp'],
        withData: false,
      );
      final String? path = result?.files.single.path;
      if (path == null) return;

      setState(() {
        _uploadingFor = result!.files.single.name;
      });
      final ClinicalDocument doc = await notifier.upload(
        File(path),
        uploadedVia: 'upload',
      );
      if (!mounted) return;
      setState(() {
        _uploadingFor = null;
      });
      AppSnack.show(context, '${doc.displayName} uploaded');
      await context.push(
        '/documents/${Uri.encodeComponent(doc.id)}/processing'
        '?patient=$_id&name=${Uri.encodeQueryComponent(doc.displayName)}',
      );
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _uploadingFor = null;
      });
      AppSnack.error(context, 'That upload did not complete. Try again.');
    }
  }
}

/// A document row: type glyph, name, date, `ConfidenceBadge`, processing
/// `StatusPill`, thumbnail.
class DocumentCard extends StatelessWidget {
  const DocumentCard({
    super.key,
    required this.document,
    this.onTap,
    this.onProcess,
    this.showProcessButton = true,
  });

  final ClinicalDocument document;
  final VoidCallback? onTap;
  final VoidCallback? onProcess;
  final bool showProcessButton;

  @override
  Widget build(BuildContext context) {
    return SurfaceCard(
      onTap: onTap,
      radius: 20,
      padding: const EdgeInsets.all(AppSpacing.sm),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          ClipRRect(
            borderRadius: AppRadii.allMd,
            child: SizedBox(
              width: 56,
              height: 64,
              child: Container(
                decoration: const BoxDecoration(gradient: AppColors.monogram),
                alignment: Alignment.center,
                child: Icon(
                  AppIcons.byName(document.documentType.icon),
                  size: 22,
                  color: AppColors.primaryDark,
                ),
              ),
            ),
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Text(
                  document.displayName,
                  style: AppTypography.titleCard.copyWith(fontSize: 14),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 2),
                Text(
                  '${document.documentType.label} • ${AppDate.date(document.documentDate)}'
                  ' • ${document.sizeLabel}',
                  style: AppTypography.bodyBullet.copyWith(fontSize: 11),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 6),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: <Widget>[
                    document.processingStatus == ProcessingStatus.complete
                        ? const StatusPill(
                            label: 'Complete',
                            variant: StatusPillVariant.approved,
                            icon: 'checkCircle',
                            dense: true,
                          )
                        : document.processingStatus == ProcessingStatus.failed
                            ? const StatusPill(
                                label: 'Failed',
                                variant: StatusPillVariant.conflict,
                                icon: 'alertTriangle',
                                dense: true,
                              )
                            : document.processingStatus ==
                                    ProcessingStatus.needsReview
                                ? const StatusPill(
                                    label: 'Needs review',
                                    variant: StatusPillVariant.needsReview,
                                    icon: 'alertTriangle',
                                    dense: true,
                                  )
                                : SoftPulse(
                                    active: true,
                                    child: StatusPill(
                                      label: document.processingStatus.label,
                                      variant: StatusPillVariant.aiGenerated,
                                      icon: 'loader',
                                      dense: true,
                                    ),
                                  ),
                    ConfidenceBadge(
                      band: ConfidenceBand.fromValue(
                          document.classificationConfidence),
                      score: document.classificationConfidence,
                      dense: true,
                    ),
                    if (document.isFallback)
                      const StatusPill(
                        label: 'Demo data',
                        variant: StatusPillVariant.demo,
                        dense: true,
                      ),
                    if (document.duplicate)
                      const StatusPill(
                        label: 'Duplicate',
                        variant: StatusPillVariant.neutral,
                        icon: 'files',
                        dense: true,
                      ),
                  ],
                ),
                if (onProcess != null && showProcessButton) ...<Widget>[
                  const SizedBox(height: AppSpacing.xs),
                  GestureDetector(
                    onTap: onProcess,
                    child: Text('Process now',
                        style: AppTypography.link.copyWith(fontSize: 12)),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}
