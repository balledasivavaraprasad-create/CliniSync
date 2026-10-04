import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/animations/motion.dart';
import '../../core/constants/enums.dart';
import '../../core/models/consultation.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_radii.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../shared/cards/ambient_background.dart';
import '../../shared/cards/clin_cards.dart';
import '../../shared/loading/states.dart';
import '../../shared/widgets/app_icons.dart';
import '../../shared/widgets/primitives.dart';
import '../state/feature_providers.dart';

/// Consultation editor — plan §9.15.
///
/// AI-prefilled sections carry an `AI` tag; Assessment / Plan / Follow-up start
/// empty with a `Doctor to complete` placeholder (plan §6.6).
class ConsultationScreen extends ConsumerStatefulWidget {
  const ConsultationScreen({
    super.key,
    required this.patientId,
    this.consultationId,
    this.specialty,
    this.briefId,
  });

  final String patientId;
  final String? consultationId;
  final String? specialty;
  final String? briefId;

  @override
  ConsumerState<ConsultationScreen> createState() => _ConsultationScreenState();
}

class _ConsultationScreenState extends ConsumerState<ConsultationScreen> {
  ({String patientId, String consultationId}) get _key => (
        patientId: widget.patientId,
        consultationId: widget.consultationId ?? ''
      );

  bool _creating = false;
  final Map<ConsultationSection, TextEditingController> _controllers =
      <ConsultationSection, TextEditingController>{};

  @override
  void dispose() {
    for (final TextEditingController c in _controllers.values) {
      c.dispose();
    }
    super.dispose();
  }

  TextEditingController _controllerFor(
    ConsultationSection section,
    ConsultationContent content,
  ) {
    final TextEditingController? existing = _controllers[section];
    if (existing != null) return existing;
    final TextEditingController created =
        TextEditingController(text: content.textFor(section));
    _controllers[section] = created;
    return created;
  }

  Future<void> _ensureDraft(ConsultationNotifier notifier) async {
    if (notifier.hasLoaded || _creating) return;
    setState(() => _creating = true);
    try {
      await notifier.createDraft(
        specialty: widget.specialty ?? Specialty.generalMedicine.wire,
        briefId: widget.briefId,
      );
    } catch (_) {
      if (mounted) AppSnack.error(context, 'Could not create a draft.');
    } finally {
      if (mounted) setState(() => _creating = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final ({String patientId, String consultationId}) key = _key;
    final AsyncSlice<Consultation> slice = ref.watch(consultationProvider(key));
    final ConsultationNotifier notifier =
        ref.read(consultationProvider(key).notifier);

    if (slice.loading && !slice.hasData && widget.consultationId == null) {
      WidgetsBinding.instance
          .addPostFrameCallback((_) => _ensureDraft(notifier));
    }

    final Consultation? consultation = slice.data;
    final ConsultationContent? content = notifier.draft;

    return PopScope<Object?>(
      canPop: !notifier.dirty,
      onPopInvokedWithResult: (bool didPop, Object? _) async {
        if (didPop) return;
        final bool? discard = await showDiscardDialog(context);
        if (discard == true && context.mounted) context.pop();
      },
      child: Scaffold(
        backgroundColor: AppColors.bgCanvas,
        body: SafeArea(
          bottom: false,
          child: Column(
            children: <Widget>[
              Stack(
                children: <Widget>[
                  const Positioned(
                      top: 0,
                      left: 0,
                      right: 0,
                      child: AmbientRibbon(height: 90, opacity: 0.2)),
                  TopBar(
                    title: 'Consultation',
                    subtitle: consultation?.versionChipLabel,
                    onLeadingTap: () => context.pop(),
                    trailing: <Widget>[
                      CircleIconButton(
                        icon: 'history',
                        tooltip: 'Version history',
                        enabled: consultation != null,
                        onTap: consultation == null
                            ? null
                            : () => context.push(
                                  '/patients/${widget.patientId}/consultation/'
                                  '${Uri.encodeComponent(consultation.id)}/versions',
                                ),
                      ),
                      CircleIconButton(
                        icon: 'moreVertical',
                        tooltip: 'More',
                        onTap: () => _showMore(context, consultation, notifier),
                      ),
                    ],
                  ),
                ],
              ),
              Expanded(
                child: slice.hasError && !slice.hasData
                    ? ErrorStateView(
                        message: slice.error!.message,
                        onRetry: notifier.load,
                      )
                    : content == null
                        ? (_creating
                            ? const Center(
                                child:
                                    CircularProgressIndicator(strokeWidth: 2))
                            : const EmptyState(
                                icon: 'pencil',
                                title: 'No draft yet',
                                message:
                                    'Start a consultation from the 60-second brief to pre-fill the AI sections.',
                              ))
                        : _Editor(
                            content: content,
                            origin: consultation?.currentVersion?.origin ??
                                ConsultationOrigin.aiGenerated,
                            status: consultation?.status ??
                                ConsultationStatus.draft,
                            notifier: notifier,
                            controllerFor: (ConsultationSection s) =>
                                _controllerFor(s, content),
                          ),
              ),
            ],
          ),
        ),
        bottomNavigationBar: content == null
            ? null
            : StickyActionBar(
                primaryLabel: 'Save Version',
                primaryIcon: 'save',
                enabled: !notifier.saving,
                onPrimary: () => _save(notifier, consultation),
                extraSecondaryIcons: <Widget>[
                  const SizedBox(width: AppSpacing.xs),
                  CircleIconButton(
                    icon: 'shieldCheck',
                    tooltip: 'Review & Approve',
                    size: 56,
                    iconSize: 22,
                    onTap: consultation == null
                        ? null
                        : () => context.push(
                              '/patients/${widget.patientId}/consultation/'
                              '${Uri.encodeComponent(consultation.id)}/approve',
                            ),
                  ),
                ],
              ),
      ),
    );
  }

  Future<void> _save(
      ConsultationNotifier notifier, Consultation? consultation) async {
    _pushToModel(notifier);
    try {
      await notifier.saveVersion(changeSummary: 'Edited by doctor');
      if (mounted) AppSnack.show(context, 'Version saved');
    } catch (_) {
      if (mounted) {
        AppSnack.error(
            context, 'Could not save. Your edits are still here — try again.');
      }
    }
  }

  void _pushToModel(ConsultationNotifier notifier) {
    final ConsultationContent? draft = notifier.draft;
    if (draft == null) return;
    _controllers.forEach(
        (ConsultationSection section, TextEditingController controller) {
      draft.setText(section, controller.text);
    });
  }

  void _showMore(
    BuildContext context,
    Consultation? consultation,
    ConsultationNotifier notifier,
  ) {
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: AppColors.bgCanvas,
      builder: (BuildContext sheetContext) => SheetScaffoldLite(
        title: 'Consultation',
        subtitle: consultation?.versionChipLabel,
        children: <Widget>[
          ListTileLite(
            iconName: 'save',
            label: 'Save as new version',
            onTap: () {
              Navigator.of(sheetContext).pop();
              _save(notifier, consultation);
            },
          ),
          ListTileLite(
            iconName: 'history',
            label: 'Version history',
            onTap: () {
              Navigator.of(sheetContext).pop();
              if (consultation == null) return;
              context.push(
                '/patients/${widget.patientId}/consultation/'
                '${Uri.encodeComponent(consultation.id)}/versions',
              );
            },
          ),
          ListTileLite(
            iconName: 'bookMarked',
            label: 'Clinical memory',
            onTap: () {
              Navigator.of(sheetContext).pop();
              context.push('/patients/${widget.patientId}/memory');
            },
          ),
        ],
      ),
    );
  }
}

class _Editor extends StatelessWidget {
  const _Editor({
    required this.content,
    required this.origin,
    required this.status,
    required this.notifier,
    required this.controllerFor,
  });

  final ConsultationContent content;
  final ConsultationOrigin origin;
  final ConsultationStatus status;
  final ConsultationNotifier notifier;
  final TextEditingController Function(ConsultationSection section)
      controllerFor;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: EdgeInsets.zero,
      children: <Widget>[
        // ── Status pills
        Padding(
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.screenH,
            AppSpacing.sm,
            AppSpacing.screenH,
            0,
          ),
          child: Wrap(
            spacing: 6,
            runSpacing: 6,
            children: <Widget>[
              StatusPill(
                label: origin.label,
                variant: origin == ConsultationOrigin.doctorEdited
                    ? StatusPillVariant.approved
                    : StatusPillVariant.aiGenerated,
                icon: origin == ConsultationOrigin.doctorEdited
                    ? 'pencil'
                    : 'sparkles',
              ),
              StatusPill(
                label: status.label,
                variant: status == ConsultationStatus.approved
                    ? StatusPillVariant.approved
                    : StatusPillVariant.neutral,
              ),
              if (notifier.dirty)
                const StatusPill(
                  label: 'Unsaved changes',
                  variant: StatusPillVariant.needsReview,
                  icon: 'alertTriangle',
                ),
              if (status == ConsultationStatus.approved)
                const StatusPill(
                  label: 'Locked after approval',
                  variant: StatusPillVariant.neutral,
                  icon: 'lock',
                ),
            ],
          ),
        ),

        const SizedBox(height: AppSpacing.md),

        // ── Editable section cards
        for (int i = 0; i < ConsultationSection.values.length; i++)
          SectionReveal(
            index: i,
            child: Padding(
              padding: EdgeInsets.fromLTRB(
                AppSpacing.screenH,
                i == 0 ? 0 : AppSpacing.xs,
                AppSpacing.screenH,
                0,
              ),
              child: _SectionEditor(
                section: ConsultationSection.values[i],
                content: content,
                readOnly: status == ConsultationStatus.approved,
                controller: controllerFor(ConsultationSection.values[i]),
                onChanged: (String value) =>
                    notifier.update(ConsultationSection.values[i], value),
              ),
            ),
          ),

        // ── AddRow
        Padding(
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.screenH,
            AppSpacing.sm,
            AppSpacing.screenH,
            0,
          ),
          child: AddRow(
            label: 'Add Section / Note',
            icon: 'plus',
            onTap: () => AppSnack.show(
              context,
              'All consultation sections are already listed. Extra notes go in Assessment or Plan.',
            ),
          ),
        ),

        const SizedBox(height: AppSpacing.md),
        const ClinicalDisclaimer(),
        const SizedBox(height: AppSpacing.stickyBarHeight),
      ],
    );
  }
}

class _SectionEditor extends StatelessWidget {
  const _SectionEditor({
    required this.section,
    required this.content,
    required this.readOnly,
    required this.controller,
    required this.onChanged,
  });

  final ConsultationSection section;
  final ConsultationContent content;
  final bool readOnly;
  final TextEditingController controller;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    final bool isList = section == ConsultationSection.currentMedications ||
        section == ConsultationSection.allergies ||
        section == ConsultationSection.investigationsReviewed;
    final bool empty = content.textFor(section).trim().isEmpty;

    return SurfaceCard(
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  section.label.toUpperCase(),
                  style: AppTypography.capsLabel.copyWith(
                    color: AppColors.textSecondary,
                    fontSize: 10.5,
                  ),
                ),
              ),
              if (section.aiPrefilled && !empty)
                const StatusPill(
                    label: 'AI',
                    variant: StatusPillVariant.aiGenerated,
                    dense: true),
              if (empty && !section.aiPrefilled)
                const StatusPill(
                  label: 'Doctor to complete',
                  variant: StatusPillVariant.needsReview,
                  dense: true,
                ),
              if (readOnly)
                Icon(AppIcons.byName('lock'),
                    size: 13, color: AppColors.textTertiary),
            ],
          ),
          const SizedBox(height: AppSpacing.xs),
          if (isList)
            _ListPreview(text: content.textFor(section))
          else
            TextField(
              controller: controller,
              readOnly: readOnly,
              maxLines: null,
              minLines: empty ? 2 : 3,
              onChanged: onChanged,
              style: AppTypography.body,
              cursorColor: AppColors.primary,
              decoration: InputDecoration(
                isDense: true,
                filled: true,
                fillColor: AppColors.surfaceTint,
                hintText: empty ? 'Doctor to complete' : null,
                hintStyle:
                    AppTypography.body.copyWith(color: AppColors.textTertiary),
                border: const OutlineInputBorder(
                  borderRadius: AppRadii.allMd,
                  borderSide: BorderSide.none,
                ),
                enabledBorder: const OutlineInputBorder(
                  borderRadius: AppRadii.allMd,
                  borderSide: BorderSide.none,
                ),
                focusedBorder: const OutlineInputBorder(
                  borderRadius: AppRadii.allMd,
                  borderSide: BorderSide(color: AppColors.primary, width: 1.4),
                ),
                contentPadding: const EdgeInsets.all(AppSpacing.sm),
              ),
            ),
        ],
      ),
    );
  }
}

class _ListPreview extends StatelessWidget {
  const _ListPreview({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    final List<String> rows = text
        .split('\n')
        .map((String s) => s.trim())
        .where((String s) => s.isNotEmpty)
        .toList(growable: false);
    if (rows.isEmpty) {
      return Text(
        'Doctor to complete',
        style: AppTypography.body.copyWith(color: AppColors.textTertiary),
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        for (final String r in rows)
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Row(
              children: <Widget>[
                Container(
                  width: 4,
                  height: 4,
                  margin: const EdgeInsets.only(right: 8),
                  decoration: const BoxDecoration(
                    color: AppColors.primary,
                    shape: BoxShape.circle,
                  ),
                ),
                Expanded(child: Text(r, style: AppTypography.bodyBullet)),
              ],
            ),
          ),
      ],
    );
  }
}

/// Version history — plan §9.16, template: reference screen 2's timeline.
class VersionHistoryScreen extends ConsumerWidget {
  const VersionHistoryScreen({
    super.key,
    required this.patientId,
    required this.consultationId,
  });

  final String patientId;
  final String consultationId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<List<ConsultationVersion>> async =
        ref.watch(consultationVersionsProvider(consultationId));
    final versions = async.valueOrNull ?? const <ConsultationVersion>[];

    return Scaffold(
      backgroundColor: AppColors.bgCanvas,
      body: SafeArea(
        bottom: false,
        child: Column(
          children: <Widget>[
            TopBar(
              title: 'Version History',
              subtitle:
                  '${versions.length} version${versions.length == 1 ? '' : 's'}',
              onLeadingTap: () => context.pop(),
            ),
            Expanded(
              child: async.isLoading
                  ? const Padding(
                      padding:
                          EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
                      child: SkeletonRail(items: 3),
                    )
                  : async.hasError
                      ? ErrorStateView(
                          message: 'Could not load the version history.',
                          onRetry: () => ref.invalidate(
                              consultationVersionsProvider(consultationId)),
                        )
                      : versions.isEmpty
                          ? const EmptyState(
                              icon: 'history',
                              title: 'No versions yet',
                              message:
                                  'Saving a version records what changed and who changed it.',
                            )
                          : ListView(
                              padding: EdgeInsets.zero,
                              children: <Widget>[
                                Padding(
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: AppSpacing.screenH,
                                    vertical: AppSpacing.md,
                                  ),
                                  child: Column(
                                    children: <Widget>[
                                      for (int i = 0; i < versions.length; i++)
                                        SectionReveal(
                                          index: i,
                                          child: Padding(
                                            padding: const EdgeInsets.only(
                                                bottom: AppSpacing.sm),
                                            child: DatedTimelineEntry(
                                              date: versions[i].createdAt,
                                              isFirst: i == 0,
                                              isLast: i == versions.length - 1,
                                              child: VersionCard(
                                                version: versions[i],
                                                isLatest: i == 0,
                                                onRestore: () => _restore(
                                                    context, ref, versions[i]),
                                              ),
                                            ),
                                          ),
                                        ),
                                    ],
                                  ),
                                ),
                                const SizedBox(height: AppSpacing.md),
                                const ClinicalDisclaimer(),
                                const SizedBox(height: AppSpacing.xxl),
                              ],
                            ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _restore(
    BuildContext context,
    WidgetRef ref,
    ConsultationVersion version,
  ) async {
    final bool? ok = await showConfirmDialog(
      context,
      title: 'Restore as draft?',
      message:
          'Version ${version.versionNumber} will be copied into a new draft version. '
          'Nothing is deleted.',
    );
    if (ok != true || !context.mounted) return;
    final ConsultationNotifier notifier = ref.read(consultationProvider(
        (patientId: patientId, consultationId: consultationId)).notifier);
    try {
      await notifier.saveVersion(
          changeSummary: 'Restored from v${version.versionNumber}');
      if (context.mounted) {
        AppSnack.show(
            context, 'Restored v${version.versionNumber} as a new draft');
        ref.invalidate(consultationVersionsProvider(consultationId));
      }
    } catch (_) {
      if (context.mounted) {
        AppSnack.error(context, 'Could not restore that version.');
      }
    }
  }
}

class VersionCard extends StatelessWidget {
  const VersionCard(
      {super.key,
      required this.version,
      this.isLatest = false,
      this.onRestore});

  final ConsultationVersion version;
  final bool isLatest;
  final VoidCallback? onRestore;

  @override
  Widget build(BuildContext context) {
    return SurfaceCard(
      radius: 20,
      padding: const EdgeInsets.all(AppSpacing.cardGap),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  'v${version.versionNumber}',
                  style: AppTypography.titleCard.copyWith(fontSize: 14.5),
                ),
              ),
              StatusPill(
                label: version.origin.label,
                variant: switch (version.origin) {
                  ConsultationOrigin.doctorEdited => StatusPillVariant.approved,
                  ConsultationOrigin.approved => StatusPillVariant.approved,
                  ConsultationOrigin.aiGenerated =>
                    StatusPillVariant.aiGenerated,
                },
                dense: true,
              ),
              if (isLatest) ...<Widget>[
                const SizedBox(width: 4),
                const StatusPill(
                    label: 'Current',
                    variant: StatusPillVariant.neutral,
                    dense: true),
              ],
            ],
          ),
          const SizedBox(height: 3),
          Text(version.stampLabel, style: AppTypography.caption),
          if ((version.changeSummary ?? '').isNotEmpty) ...<Widget>[
            const SizedBox(height: 5),
            Text(version.changeSummary!, style: AppTypography.bodyBullet),
          ],
          const SizedBox(height: AppSpacing.xs),
          Row(
            children: <Widget>[
              GestureDetector(
                onTap: () => _view(context),
                child: Text('View',
                    style: AppTypography.link.copyWith(fontSize: 12)),
              ),
              if (onRestore != null) ...<Widget>[
                const SizedBox(width: AppSpacing.md),
                GestureDetector(
                  onTap: onRestore,
                  child: Text('Restore as draft',
                      style: AppTypography.link.copyWith(fontSize: 12)),
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }

  void _view(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.bgCanvas,
      builder: (BuildContext sheetContext) => DraggableScrollableSheet(
        initialChildSize: 0.8,
        minChildSize: 0.4,
        maxChildSize: 0.94,
        expand: false,
        builder: (BuildContext context, ScrollController controller) =>
            SheetScaffoldLite(
          title: 'v${version.versionNumber} · ${version.origin.label}',
          subtitle: version.stampLabel,
          scrollController: controller,
          children: <Widget>[
            for (final ConsultationSection s in ConsultationSection.values)
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                child: SurfaceCard(
                  padding: const EdgeInsets.all(AppSpacing.md),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        s.label.toUpperCase(),
                        style: AppTypography.capsLabel.copyWith(
                          color: AppColors.textSecondary,
                          fontSize: 10,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        version.content?.textFor(s).trim().isEmpty ?? true
                            ? 'Not recorded'
                            : version.content!.textFor(s),
                        style: AppTypography.body,
                      ),
                    ],
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// Compact list tile used in the "more" sheets.
class ListTileLite extends StatelessWidget {
  const ListTileLite(
      {super.key,
      required this.iconName,
      required this.label,
      required this.onTap});

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

/// Minimal sheet scaffold for this file.
class SheetScaffoldLite extends StatelessWidget {
  const SheetScaffoldLite({
    super.key,
    required this.title,
    required this.children,
    this.subtitle,
    this.scrollController,
  });

  final String title;
  final String? subtitle;
  final List<Widget> children;
  final ScrollController? scrollController;

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
              AppSpacing.screenH,
              AppSpacing.md,
              AppSpacing.screenH,
              0,
            ),
            child: Row(
              children: <Widget>[
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      Text(title, style: AppTypography.titleScreen),
                      if (subtitle != null)
                        Text(subtitle!, style: AppTypography.titleScreenSub),
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
          Flexible(
            child: scrollController == null
                ? Column(mainAxisSize: MainAxisSize.min, children: children)
                : ListView(
                    controller: scrollController,
                    padding: const EdgeInsets.fromLTRB(
                      AppSpacing.screenH,
                      AppSpacing.sm,
                      AppSpacing.screenH,
                      AppSpacing.md,
                    ),
                    children: children,
                  ),
          ),
          if (scrollController == null) const SizedBox(height: AppSpacing.md),
        ],
      ),
    );
  }
}

/// Unsaved-changes guard — plan §9.15.
Future<bool?> showDiscardDialog(BuildContext context) {
  return showDialog<bool>(
    context: context,
    builder: (BuildContext dialogContext) => AlertDialog(
      title: Text('Discard unsaved changes?',
          style: AppTypography.titleHeader.copyWith(fontSize: 18)),
      content: Text(
        'Your edits to this consultation have not been saved as a version.',
        style: AppTypography.body,
      ),
      actions: <Widget>[
        TextButton(
          onPressed: () => Navigator.of(dialogContext).pop(false),
          child: const Text('Keep editing'),
        ),
        TextButton(
          onPressed: () => Navigator.of(dialogContext).pop(true),
          child: Text('Discard',
              style: AppTypography.link.copyWith(color: AppColors.danger)),
        ),
      ],
    ),
  );
}

/// Confirmation dialog used by Restore-as-draft.
Future<bool?> showConfirmDialog(
  BuildContext context, {
  required String title,
  required String message,
}) {
  return showDialog<bool>(
    context: context,
    builder: (BuildContext dialogContext) => AlertDialog(
      title:
          Text(title, style: AppTypography.titleHeader.copyWith(fontSize: 18)),
      content: Text(message, style: AppTypography.body),
      actions: <Widget>[
        TextButton(
          onPressed: () => Navigator.of(dialogContext).pop(false),
          child: const Text('Cancel'),
        ),
        TextButton(
          onPressed: () => Navigator.of(dialogContext).pop(true),
          child: const Text('Continue'),
        ),
      ],
    ),
  );
}
