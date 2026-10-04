import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/animations/motion.dart';
import '../../core/constants/enums.dart';
import '../../core/models/clinical_fact.dart';
import '../../core/networking/api_exception.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/utils/confidence_band.dart';
import '../../core/utils/date_format.dart';
import '../../shared/cards/clin_cards.dart';
import '../../shared/loading/states.dart';
import '../../shared/widgets/app_icons.dart';
import '../../shared/widgets/primitives.dart';
import '../state/feature_providers.dart';

/// Evidence — plan §9.6, the trust layer.
///
/// Answers "Why does the system believe this?" with the fact, its confidence,
/// its verification state, the source document, and the exact verbatim span.
class EvidenceScreen extends ConsumerWidget {
  const EvidenceScreen({super.key, required this.factId});

  final String factId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<FactEvidence> async = ref.watch(evidenceProvider(factId));

    return Scaffold(
      backgroundColor: AppColors.bgCanvas,
      body: SafeArea(
        bottom: false,
        child: Column(
          children: <Widget>[
            TopBar(
              title: 'Evidence',
              subtitle: 'Why the system believes this',
              onLeadingTap: () => context.pop(),
              trailing: <Widget>[
                CircleIconButton(
                  icon: 'refreshCw',
                  tooltip: 'Reload',
                  onTap: () => ref.invalidate(evidenceProvider(factId)),
                ),
              ],
            ),
            Expanded(
              child: async.when(
                loading: () => const Padding(
                  padding: EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
                  child: Column(
                    children: <Widget>[
                      SkeletonCard(height: 130),
                      SizedBox(height: AppSpacing.lg),
                      SkeletonCard(height: 220),
                    ],
                  ),
                ),
                error: (Object e, StackTrace _) => ErrorStateView(
                  message: ErrorText.of(e),
                  onRetry: () => ref.invalidate(evidenceProvider(factId)),
                ),
                data: (FactEvidence evidence) =>
                    _EvidenceBody(evidence: evidence),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Maps a thrown object to human text without showing the raw exception
/// (plan §6.6 rule 7).
abstract final class ErrorText {
  static String of(Object error) => error is ApiException
      ? error.message
      : 'We couldn\'t load that. Try again.';
}

class _EvidenceBody extends StatelessWidget {
  const _EvidenceBody({required this.evidence});

  final FactEvidence evidence;

  @override
  Widget build(BuildContext context) {
    final EvidenceSource source = evidence.source;

    return ListView(
      padding: EdgeInsets.zero,
      children: <Widget>[
        // ── Fact summary card
        SectionReveal(
          index: 0,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.screenH,
              AppSpacing.md,
              AppSpacing.screenH,
              0,
            ),
            child: SurfaceCard(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Row(
                    children: <Widget>[
                      Icon(
                        AppIcons.byName(evidence.factType.icon),
                        size: 18,
                        color: AppColors.primary,
                      ),
                      const SizedBox(width: 6),
                      Text(
                        evidence.factType.label.toUpperCase(),
                        style: AppTypography.capsLabel
                            .copyWith(color: AppColors.textSecondary),
                      ),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    evidence.value,
                    style: AppTypography.titleHeader.copyWith(fontSize: 20),
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: <Widget>[
                      ConfidenceBadge(
                        band: evidence.confidenceBand,
                        score: evidence.confidence,
                      ),
                      StatusPill(
                        label: evidence.verificationStatus.label,
                        variant: switch (evidence.verificationStatus) {
                          VerificationStatus.doctorVerified =>
                            StatusPillVariant.approved,
                          VerificationStatus.needsVerification =>
                            StatusPillVariant.needsReview,
                          VerificationStatus.doctorRejected =>
                            StatusPillVariant.conflict,
                          VerificationStatus.unverified =>
                            StatusPillVariant.aiGenerated,
                        },
                      ),
                      if (evidence.provenanceVerified)
                        const StatusPill(
                          label: 'Provenance verified',
                          variant: StatusPillVariant.approved,
                          icon: 'shieldCheck',
                        ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),

        const SizedBox(height: AppSpacing.lg),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
          child: Text('Source', style: AppTypography.titleSection),
        ),
        const SizedBox(height: AppSpacing.sm),

        // ── Source row + verbatim quote
        SectionReveal(
          index: 1,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
            child: EvidenceCard(
              sourceTitle: source.documentFilename,
              sourceMeta:
                  '${source.documentType.label} • ${AppDate.date(source.documentDate)}',
              pageChip: source.pageChipLabel,
              verbatim: source.verbatimText,
              highlight: source.hasVerbatim ? source.verbatimText : null,
              confidenceBand: evidence.confidenceBand,
              confidence: evidence.confidence,
              provenanceVerified: evidence.provenanceVerified,
            ),
          ),
        ),

        // ── Provenance explanation
        SectionReveal(
          index: 2,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.screenH,
              AppSpacing.md,
              AppSpacing.screenH,
              0,
            ),
            child: ClinNoticeBanner(
              message: evidence.provenanceVerified
                  ? 'The quoted text was matched back to the stored document text, so this claim is traceable.'
                  : 'This claim could not be matched back to an exact span in the stored text. Treat it as unverified.',
              icon:
                  evidence.provenanceVerified ? 'shieldCheck' : 'alertTriangle',
              tone: evidence.provenanceVerified
                  ? ClinNoticeTone.primary
                  : ClinNoticeTone.warning,
            ),
          ),
        ),

        const SizedBox(height: AppSpacing.lg),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
          child: Text('How to read this', style: AppTypography.titleSection),
        ),
        const SizedBox(height: AppSpacing.sm),
        const SectionReveal(
          index: 3,
          child: Padding(
            padding: EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
            child: SurfaceCard(
              padding: EdgeInsets.all(AppSpacing.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  _LegendRow(
                    color: AppColors.confidenceHigh,
                    label: 'High · ≥0.85',
                    detail:
                        'Read directly from the source with a confident match.',
                  ),
                  SizedBox(height: AppSpacing.xs),
                  _LegendRow(
                    color: AppColors.confidenceMedium,
                    label: 'Medium · 0.60–0.84',
                    detail:
                        'Extracted from the source, but the mapping is partly inferred.',
                  ),
                  SizedBox(height: AppSpacing.xs),
                  _LegendRow(
                    color: AppColors.confidenceLow,
                    label: 'Needs verification · <0.60',
                    detail:
                        'Weak read of the source. Confirm against the original document.',
                  ),
                ],
              ),
            ),
          ),
        ),

        const SizedBox(height: AppSpacing.lg),
        const ClinicalDisclaimer(),
        const SizedBox(height: AppSpacing.xxl),
      ],
    );
  }
}

class _LegendRow extends StatelessWidget {
  const _LegendRow(
      {required this.color, required this.label, required this.detail});

  final Color color;
  final String label;
  final String detail;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Container(
          width: 10,
          height: 10,
          margin: const EdgeInsets.only(top: 4),
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(label,
                  style: AppTypography.bodyStrong.copyWith(fontSize: 13)),
              Text(detail,
                  style: AppTypography.bodyBullet.copyWith(fontSize: 11.5)),
            ],
          ),
        ),
      ],
    );
  }
}

/// Extracted clinical facts for a patient — reached from the Overview stat strip
/// and the Processing screen (plan §6.3 "Clinical Facts").
class FactsScreen extends ConsumerStatefulWidget {
  const FactsScreen({super.key, required this.patientId});

  final String patientId;

  @override
  ConsumerState<FactsScreen> createState() => _FactsScreenState();
}

class _FactsScreenState extends ConsumerState<FactsScreen> {
  int _type = 0;
  int _status = 0;

  static const List<String> _typeLabels = <String>[
    'All',
    'Diagnoses',
    'Symptoms',
    'Medications',
    'Results',
    'Allergies',
  ];

  static const List<String> _statusLabels = <String>[
    'All',
    'Unverified',
    'Needs verification',
    'Doctor approved',
  ];

  @override
  Widget build(BuildContext context) {
    final AsyncSlice<List<ClinicalFact>> slice =
        ref.watch(factsProvider(widget.patientId));
    final List<ClinicalFact> all = slice.data ?? const <ClinicalFact>[];
    final List<ClinicalFact> visible = _filter(all);

    return Scaffold(
      backgroundColor: AppColors.bgCanvas,
      body: SafeArea(
        bottom: false,
        child: RefreshIndicator(
          color: AppColors.primary,
          onRefresh: () =>
              ref.read(factsProvider(widget.patientId).notifier).refresh(),
          child: ListView(
            padding: EdgeInsets.zero,
            children: <Widget>[
              TopBar(
                title: 'Clinical Facts',
                subtitle: '${all.length} extracted from source records',
                onLeadingTap: () => context.pop(),
              ),
              SectionReveal(
                index: 0,
                child: Padding(
                  padding: const EdgeInsets.only(
                      top: AppSpacing.sm, bottom: AppSpacing.xs),
                  child: PillTabs(
                    labels: _typeLabels,
                    selectedIndex: _type,
                    onChanged: (int i) => setState(() => _type = i),
                  ),
                ),
              ),
              SectionReveal(
                index: 1,
                child: Padding(
                  padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                  child: PillTabs(
                    labels: _statusLabels,
                    selectedIndex: _status,
                    onChanged: (int i) => setState(() => _status = i),
                  ),
                ),
              ),
              if (slice.loading && !slice.hasData)
                const Padding(
                  padding: EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
                  child: Column(
                    children: <Widget>[
                      SkeletonCard(height: 96),
                      SizedBox(height: AppSpacing.xs),
                      SkeletonCard(height: 96),
                    ],
                  ),
                )
              else if (slice.hasError && all.isEmpty)
                ErrorStateView(
                  message: slice.error!.message,
                  onRetry: () => ref
                      .read(factsProvider(widget.patientId).notifier)
                      .refresh(),
                )
              else if (visible.isEmpty)
                EmptyState(
                  icon: 'sparkles',
                  title: all.isEmpty
                      ? 'No facts extracted yet'
                      : 'Nothing in this filter',
                  message: all.isEmpty
                      ? 'Upload a record and ClinSync will extract diagnoses, medications and results with their source.'
                      : 'Try a different filter.',
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
                            child: FactCard(fact: visible[i]),
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
      ),
    );
  }

  List<ClinicalFact> _filter(List<ClinicalFact> all) {
    return all.where((ClinicalFact f) {
      final bool typeOk = switch (_type) {
        0 => true,
        1 => f.factType == FactType.diagnosis,
        2 => f.factType == FactType.symptom,
        3 => f.factType == FactType.medication,
        4 => f.factType == FactType.investigation,
        _ => f.factType == FactType.allergy,
      };
      final bool statusOk = switch (_status) {
        0 => true,
        1 => f.verificationStatus == VerificationStatus.unverified,
        2 => f.verificationStatus == VerificationStatus.needsVerification,
        _ => f.verificationStatus == VerificationStatus.doctorVerified,
      };
      return typeOk && statusOk;
    }).toList(growable: false);
  }
}

/// A clinical fact row: value, confidence, verification, evidence entry point.
class FactCard extends ConsumerWidget {
  const FactCard({super.key, required this.fact, this.patientId});

  final ClinicalFact fact;
  final String? patientId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return SurfaceCard(
      onTap: () =>
          context.push('/facts/${Uri.encodeComponent(fact.id)}/evidence'),
      radius: 20,
      padding: const EdgeInsets.all(AppSpacing.cardGap),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Container(
                width: 32,
                height: 32,
                decoration: const BoxDecoration(
                  color: AppColors.primarySoft,
                  shape: BoxShape.circle,
                ),
                alignment: Alignment.center,
                child: Icon(
                  AppIcons.byName(fact.factType.icon),
                  size: 15,
                  color: AppColors.primaryDark,
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    Text(
                      fact.value,
                      style: AppTypography.titleCard.copyWith(fontSize: 14),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '${fact.factType.label} • ${AppDate.date(fact.factDate)}',
                      style: AppTypography.bodyBullet.copyWith(fontSize: 11),
                    ),
                  ],
                ),
              ),
              Icon(AppIcons.byName('chevronRight'),
                  size: 18, color: AppColors.textTertiary),
            ],
          ),
          const SizedBox(height: AppSpacing.xs),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: <Widget>[
              ConfidenceBadge(
                  band: fact.confidenceBand,
                  score: fact.confidence,
                  dense: true),
              StatusPill(
                label: fact.verificationStatus.label,
                variant: switch (fact.verificationStatus) {
                  VerificationStatus.doctorVerified =>
                    StatusPillVariant.approved,
                  VerificationStatus.needsVerification =>
                    StatusPillVariant.needsReview,
                  VerificationStatus.doctorRejected =>
                    StatusPillVariant.conflict,
                  VerificationStatus.unverified =>
                    StatusPillVariant.aiGenerated,
                },
                dense: true,
              ),
              if (fact.provenanceVerified)
                const StatusPill(
                  label: 'Provenance',
                  variant: StatusPillVariant.approved,
                  icon: 'shieldCheck',
                  dense: true,
                ),
              StatusPill(
                label: fact.pageChipLabel,
                variant: StatusPillVariant.neutral,
                dense: true,
              ),
            ],
          ),
        ],
      ),
    );
  }
}
