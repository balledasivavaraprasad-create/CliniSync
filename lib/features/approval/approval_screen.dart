import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/animations/motion.dart';
import '../../core/constants/enums.dart';
import '../../core/models/consultation.dart';
import '../../core/networking/api_exception.dart';
import '../../core/repositories/providers.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/utils/date_format.dart';
import '../../shared/cards/ambient_background.dart';
import '../../shared/cards/clin_cards.dart';
import '../../shared/loading/states.dart';
import '../../shared/widgets/app_icons.dart';
import '../../shared/widgets/primitives.dart';
import '../overview/overview_tab_bodies.dart';
import '../state/feature_providers.dart';

/// Approval — plan §9.17.
///
/// Makes the Draft → Review → Approve → Verified Memory transition unmistakable:
/// a pass card summarising what will enter memory, a review-progress ring, the
/// required acknowledgements, the memory preview, and a success state.
class ApprovalScreen extends ConsumerStatefulWidget {
  const ApprovalScreen({
    super.key,
    required this.patientId,
    required this.consultationId,
  });

  final String patientId;
  final String consultationId;

  @override
  ConsumerState<ApprovalScreen> createState() => _ApprovalScreenState();
}

class _ApprovalScreenState extends ConsumerState<ApprovalScreen> {
  final Set<String> _acknowledged = <String>{};
  bool _approving = false;
  bool _succeeded = false;
  ApprovalResult? _result;

  ({String consultationId, bool acknowledged}) get _key => (
        consultationId: widget.consultationId,
        acknowledged: _acknowledged.isNotEmpty
      );

  @override
  Widget build(BuildContext context) {
    if (_succeeded && _result != null) {
      return _SuccessState(
        result: _result!,
        patientId: widget.patientId,
        onBack: () => context.go('/patients/${widget.patientId}/memory'),
      );
    }

    final AsyncValue<ApprovalPreview> async =
        ref.watch(approvalPreviewProvider(_key));
    final AsyncSlice<Consultation> slice = ref.watch(consultationProvider(
        (patientId: widget.patientId, consultationId: widget.consultationId)));

    final ApprovalPreview? preview = async.valueOrNull;
    final bool allAcknowledged =
        _acknowledged.length >= (preview?.requiredAcknowledgements ?? 0);
    final bool canApprove =
        (preview?.canApprove ?? false) && allAcknowledged && preview != null;

    return Scaffold(
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
                  title: 'Approval',
                  subtitle: slice.data?.versionChipLabel,
                  onLeadingTap: () => context.pop(),
                ),
              ],
            ),
            Expanded(
              child: async.isLoading
                  ? const Padding(
                      padding:
                          EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
                      child: Column(
                        children: <Widget>[
                          SkeletonCard(height: 160),
                          SizedBox(height: AppSpacing.lg),
                          SkeletonCard(height: 140),
                          SizedBox(height: AppSpacing.lg),
                          SkeletonCard(height: 200),
                        ],
                      ),
                    )
                  : async.hasError || preview == null
                      ? ErrorStateView(
                          message: 'We couldn\'t run the approval checks.',
                          onRetry: () =>
                              ref.invalidate(approvalPreviewProvider(_key)),
                        )
                      : _ApprovalBody(
                          preview: preview,
                          acknowledged: _acknowledged,
                          canApprove: canApprove,
                          onToggle: (String name, bool value) => setState(() {
                            if (value) {
                              _acknowledged.add(name);
                            } else {
                              _acknowledged.remove(name);
                            }
                          }),
                          onRecompute: () =>
                              ref.invalidate(approvalPreviewProvider(_key)),
                        ),
            ),
          ],
        ),
      ),
      bottomNavigationBar: StickyActionBar(
        primaryLabel: 'Approve & Update Memory',
        primaryIcon: 'shieldCheck',
        enabled: canApprove && !_approving,
        tooltip: canApprove ? null : 'Tick the required acknowledgements first',
        onPrimary: canApprove ? _approve : null,
        extraSecondaryIcons: <Widget>[
          const SizedBox(width: AppSpacing.xs),
          CircleIconButton(
            icon: 'bookMarked',
            tooltip: 'Clinical memory',
            size: 56,
            iconSize: 22,
            onTap: () => context.push('/patients/${widget.patientId}/memory'),
          ),
        ],
      ),
    );
  }

  Future<void> _approve() async {
    setState(() => _approving = true);
    try {
      final ApprovalResult result = await ref
          .read(consultationRepositoryProvider)
          .approve(widget.consultationId, acknowledgedUnedited: true);
      if (!mounted) return;
      setState(() {
        _result = result;
        _succeeded = true;
      });
      // Refresh everything the approval touched (plan §11.3).
      ref.invalidate(memoryProvider(widget.patientId));
      ref.invalidate(overviewProvider(widget.patientId));
      ref.invalidate(memoryHistoryProvider(widget.patientId));
      ref.invalidate(issuesProvider(widget.patientId));
    } on ApiException catch (e) {
      if (!mounted) return;
      if (e.code.toUpperCase() == 'GATE1_BLOCKED' ||
          e.code.toUpperCase() == 'CONSULTATION_NOT_APPROVABLE') {
        AppSnack.error(
            context, 'Approval is on hold: some items need your review.');
        ref.invalidate(approvalPreviewProvider(_key));
      } else {
        AppSnack.error(context, e.message);
      }
    } finally {
      if (mounted) setState(() => _approving = false);
    }
  }
}

class _ApprovalBody extends StatelessWidget {
  const _ApprovalBody({
    required this.preview,
    required this.acknowledged,
    required this.canApprove,
    required this.onToggle,
    required this.onRecompute,
  });

  final ApprovalPreview preview;
  final Set<String> acknowledged;
  final bool canApprove;
  // ignore: avoid_positional_boolean_parameters — callback signature mirrors `onChanged`.
  final void Function(String name, bool value) onToggle;
  final VoidCallback onRecompute;

  /// Why approval is on hold, phrased for whoever is reading it.
  ///
  /// Gate 1 fails closed when the faithfulness judge is unreachable. That is the
  /// safe outcome, but it is a temporary outage rather than a defect in the
  /// doctor's draft, so it gets its own wording: "try again", not "fix your
  /// notes".
  static String _blockedMessage(ApprovalPreview preview) {
    if (preview.blockedByInfrastructure) {
      return 'The automated faithfulness check could not run, so approval is '
          'paused to keep unverified content out of clinical memory. Nothing '
          'here is wrong with your notes — try again in a moment.';
    }
    if (preview.blockers.isEmpty) {
      return 'This consultation cannot be approved yet.';
    }
    return 'Approval is on hold. ${preview.blockers.length} item'
        '${preview.blockers.length == 1 ? '' : 's'} must be acknowledged '
        'first. Nothing will be marked approved until they are.';
  }

  @override
  Widget build(BuildContext context) {
    final List<ApprovalCheck> required = <ApprovalCheck>[
      ...preview.blockers,
      ...preview.warnings
    ];
    final int done = required
        .where((ApprovalCheck c) => acknowledged.contains(c.name))
        .length;

    return ListView(
      padding: EdgeInsets.zero,
      children: <Widget>[
        // ── TicketCard summarising what will enter memory
        SectionReveal(
          index: 0,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.screenH,
              AppSpacing.md,
              AppSpacing.screenH,
              0,
            ),
            child: TicketCard(
              headerLabel: 'READY FOR REVIEW',
              statusLabel: preview.outcome.label,
              headerIconName: 'shieldCheck',
              connectorIconName: 'arrowLeftRight',
              connectorCaption: 'Into memory',
              leftBlock: TicketRouteBlock(
                label: 'Draft',
                code: '${preview.proposedMemoryItems.length}',
                time: 'memory items',
                codeStyle: AppTypography.numberLarge,
              ),
              rightBlock: TicketRouteBlock(
                label: 'Checks',
                code:
                    '${preview.checks.where((ApprovalCheck c) => c.passed).length}/'
                    '${preview.checks.length}',
                time: preview.canApprove ? 'can approve' : 'blocked',
                alignEnd: true,
                codeStyle: AppTypography.numberLarge,
              ),
              keyValues: <Widget>[
                KeyValueCell(label: 'Outcome', value: preview.outcome.label),
                KeyValueCell(
                    label: 'Blocking', value: '${preview.blockers.length}'),
                KeyValueCell(
                    label: 'Warnings', value: '${preview.warnings.length}'),
              ],
              trailingTile: const EvidenceTile(label: 'Preview'),
            ),
          ),
        ),

        if (!preview.canApprove)
          SectionReveal(
            index: 1,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.screenH,
                AppSpacing.md,
                AppSpacing.screenH,
                0,
              ),
              // An infrastructure outage reads differently from a problem with
              // the note: nothing is wrong with the doctor's draft, and the fix
              // is to try again rather than to edit it.
              child: ClinNoticeBanner(
                message: _blockedMessage(preview),
                tone: ClinNoticeTone.warning,
                icon: preview.blockedByInfrastructure
                    ? 'wifiOff'
                    : 'alertTriangle',
              ),
            ),
          ),

        const SizedBox(height: AppSpacing.md),

        // ── Review progress ring
        SectionReveal(
          index: 2,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
            child: ReviewProgressStrip(
              reviewed: done,
              total: required.length,
              onTap: onRecompute,
            ),
          ),
        ),

        const SizedBox(height: AppSpacing.md),

        // ── Required acknowledgements
        if (required.isNotEmpty)
          SectionReveal(
            index: 3,
            child: Padding(
              padding:
                  const EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text('Required acknowledgements',
                      style: AppTypography.titleSection),
                  const SizedBox(height: AppSpacing.sm),
                  for (final ApprovalCheck c in required)
                    Padding(
                      padding: const EdgeInsets.only(bottom: AppSpacing.xs),
                      child: _CheckTile(
                        check: c,
                        value: acknowledged.contains(c.name),
                        onChanged: (bool v) => onToggle(c.name, v),
                      ),
                    ),
                ],
              ),
            ),
          ),

        // ── All checks
        SectionReveal(
          index: 4,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.screenH,
              AppSpacing.md,
              AppSpacing.screenH,
              AppSpacing.xs,
            ),
            child: Text('All checks', style: AppTypography.titleSection),
          ),
        ),
        SectionReveal(
          index: 5,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
            child: SurfaceCard(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Column(
                children: <Widget>[
                  for (int i = 0; i < preview.checks.length; i++)
                    Padding(
                      padding: EdgeInsets.only(
                        bottom:
                            i == preview.checks.length - 1 ? 0 : AppSpacing.xs,
                      ),
                      child: _CheckRow(check: preview.checks[i]),
                    ),
                ],
              ),
            ),
          ),
        ),

        const SizedBox(height: AppSpacing.lg),

        // ── Memory preview
        SectionReveal(
          index: 6,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.screenH,
              0,
              AppSpacing.screenH,
              AppSpacing.xs,
            ),
            child: Text('Will enter clinical memory',
                style: AppTypography.titleSection),
          ),
        ),
        SectionReveal(
          index: 7,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
            child: preview.proposedMemoryItems.isEmpty
                ? const ClinNoticeBanner(
                    message: 'No memory items are proposed from this draft.',
                    icon: 'info',
                    tone: ClinNoticeTone.neutral,
                  )
                : Column(
                    children: <Widget>[
                      for (final ProposedMemoryItem item
                          in preview.proposedMemoryItems)
                        Padding(
                          padding: const EdgeInsets.only(bottom: AppSpacing.xs),
                          child: SurfaceCard(
                            accentLeft: true,
                            padding: const EdgeInsets.all(AppSpacing.cardGap),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: <Widget>[
                                Row(
                                  children: <Widget>[
                                    Text(
                                      item.type.label.toUpperCase(),
                                      style: AppTypography.capsLabel.copyWith(
                                        color: AppColors.textSecondary,
                                        fontSize: 9.5,
                                      ),
                                    ),
                                    const Spacer(),
                                    const StatusPill(
                                      label: 'New',
                                      variant: StatusPillVariant.approved,
                                      dense: true,
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 4),
                                Text(item.value, style: AppTypography.body),
                              ],
                            ),
                          ),
                        ),
                    ],
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

class _CheckTile extends StatelessWidget {
  const _CheckTile(
      {required this.check, required this.value, required this.onChanged});

  final ApprovalCheck check;
  final bool value;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    return SurfaceCard(
      onTap: () => onChanged(!value),
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          SizedBox(
            width: 22,
            height: 22,
            child: Checkbox(
              value: value,
              onChanged: (bool? v) => onChanged(v ?? false),
            ),
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Row(
                  children: <Widget>[
                    Expanded(
                      child: Text(
                        check.label,
                        style:
                            AppTypography.bodyStrong.copyWith(fontSize: 13.5),
                      ),
                    ),
                    StatusPill(
                      label: check.severity.label,
                      variant: check.severity == CheckSeverity.block
                          ? StatusPillVariant.conflict
                          : StatusPillVariant.needsReview,
                      dense: true,
                    ),
                  ],
                ),
                const SizedBox(height: 3),
                Text(check.detail,
                    style: AppTypography.bodyBullet.copyWith(fontSize: 11.5)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _CheckRow extends StatelessWidget {
  const _CheckRow({required this.check});

  final ApprovalCheck check;

  @override
  Widget build(BuildContext context) {
    final Color color = check.passed
        ? AppColors.primary
        : check.severity == CheckSeverity.block
            ? AppColors.danger
            : AppColors.warning;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Icon(
          AppIcons.byName(check.passed ? 'checkCircle' : 'alertTriangle'),
          size: 15,
          color: color,
        ),
        const SizedBox(width: AppSpacing.xs),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(
                check.label,
                style: AppTypography.bodyStrong
                    .copyWith(fontSize: 12.5, color: color),
              ),
              Text(
                check.detail,
                style: AppTypography.caption.copyWith(fontSize: 10.5),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

/// Subtle, celebratory-but-restrained success state — plan §9.17.
class _SuccessState extends StatelessWidget {
  const _SuccessState(
      {required this.result, required this.patientId, required this.onBack});

  final ApprovalResult result;
  final String patientId;
  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bgCanvas,
      body: SafeArea(
        child: Column(
          children: <Widget>[
            const TopBar(
                title: 'Approval', subtitle: 'Completed', showLeading: false),
            Expanded(
              child: ListView(
                children: <Widget>[
                  const SizedBox(height: AppSpacing.xl),
                  SectionReveal(
                    index: 0,
                    child: Center(
                      child: _CheckCircleBurst(),
                    ),
                  ),
                  SectionReveal(
                    index: 1,
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(
                        AppSpacing.screenH,
                        AppSpacing.lg,
                        AppSpacing.screenH,
                        0,
                      ),
                      child: Column(
                        children: <Widget>[
                          Text(
                            'Clinical memory updated',
                            style: AppTypography.titlePage,
                            textAlign: TextAlign.center,
                          ),
                          const SizedBox(height: AppSpacing.xs),
                          Text(
                            '${result.memoryItemsCreated} verified item'
                            '${result.memoryItemsCreated == 1 ? '' : 's'} added. '
                            'The consultation is now locked and cannot be edited.',
                            style: AppTypography.body
                                .copyWith(color: AppColors.textSecondary),
                            textAlign: TextAlign.center,
                          ),
                        ],
                      ),
                    ),
                  ),
                  SectionReveal(
                    index: 2,
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(
                        AppSpacing.screenH,
                        AppSpacing.xl,
                        AppSpacing.screenH,
                        0,
                      ),
                      child: Column(
                        children: <Widget>[
                          KeyValueCell(
                            label: 'Approved by',
                            value: result.approvedBy ?? 'doc_001',
                          ),
                          const SizedBox(height: AppSpacing.sm),
                          KeyValueCell(
                            label: 'Approved at',
                            value: AppDateStamp.of(result.approvedAt),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const ClinicalDisclaimer(),
                ],
              ),
            ),
          ],
        ),
      ),
      bottomNavigationBar: StickyActionBar(
        primaryLabel: 'Back to Patient',
        primaryIcon: 'arrowLeft',
        onPrimary: onBack,
      ),
    );
  }
}

/// The check-circle animation on success.
class _CheckCircleBurst extends StatefulWidget {
  @override
  State<_CheckCircleBurst> createState() => _CheckCircleBurstState();
}

class _CheckCircleBurstState extends State<_CheckCircleBurst>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 700),
  )..forward();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ScaleTransition(
      scale: CurvedAnimation(parent: _controller, curve: Curves.easeOutBack),
      child: Container(
        width: 88,
        height: 88,
        decoration: const BoxDecoration(
            color: AppColors.primarySoft, shape: BoxShape.circle),
        alignment: Alignment.center,
        child: FadeTransition(
          opacity: _controller,
          child: Container(
            width: 56,
            height: 56,
            decoration: const BoxDecoration(
                color: AppColors.primary, shape: BoxShape.circle),
            alignment: Alignment.center,
            child: Icon(AppIcons.byName('check'),
                size: 28, color: AppColors.onPrimary),
          ),
        ),
      ),
    );
  }
}

/// Tiny date helper for the success state.
abstract final class AppDateStamp {
  static String of(Object? raw) {
    final DateTime? d = AppDate.tryParse(raw);
    return d == null ? '—' : AppDate.stamp(d);
  }
}
