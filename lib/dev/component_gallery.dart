import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/app_spacing.dart';
import '../core/theme/app_typography.dart';
import '../core/utils/confidence_band.dart';
import '../shared/cards/clin_cards.dart';
import '../shared/loading/states.dart';
import '../shared/navigation/bottom_nav.dart';
import '../shared/widgets/app_icons.dart';
import '../shared/widgets/primitives.dart';

/// `ComponentGallery` — task C08 / C10 acceptance. Renders every §7.6 component
/// in all of its states so it can be compared with the reference image.
class ComponentGallery extends StatelessWidget {
  const ComponentGallery({super.key});

  @override
  Widget build(BuildContext context) {
    return _Shell(
      title: 'Component gallery',
      subtitle: 'Every §7.6 component in all states',
      children: <Widget>[
        const _Section('CircleIconButton'),
        const Wrap(
          spacing: AppSpacing.xs,
          runSpacing: AppSpacing.xs,
          children: <Widget>[
            CircleIconButton(icon: 'arrowLeft'),
            CircleIconButton(icon: 'bookmark'),
            CircleIconButton(icon: 'bell'),
            CircleIconButton(icon: 'moreVertical'),
            CircleIconButton(icon: 'sliders'),
            CircleIconButton(icon: 'mic', filled: true),
            CircleIconButton(icon: 'camera', filled: true),
            CircleIconButton(icon: 'search', enabled: false),
            CircleIconButton(icon: 'search', size: 56, iconSize: 24),
          ],
        ),
        const _Section('PrimaryPillButton'),
        const Column(
          children: <Widget>[
            PrimaryPillButton(
                label: 'Generate Brief', icon: 'sparkles', onPressed: _noop),
            SizedBox(height: AppSpacing.xs),
            Row(
              children: <Widget>[
                Expanded(
                  child: PrimaryPillButton(
                    label: 'Disabled',
                    icon: 'lock',
                    enabled: false,
                    onPressed: null,
                  ),
                ),
                SizedBox(width: AppSpacing.xs),
                Expanded(
                  child: PrimaryPillButton(
                    label: 'Save',
                    icon: 'save',
                    onPressed: _noop,
                  ),
                ),
              ],
            ),
          ],
        ),
        const _Section('SectionHeader · SearchPill · PageDots'),
        const SectionHeader(title: 'Recent Patients', linkLabel: 'See all'),
        const SizedBox(height: AppSpacing.sm),
        const SearchPill(hint: 'Search patients or records'),
        const SizedBox(height: AppSpacing.sm),
        const PageDots(count: 3, activeIndex: 1),
        const _Section('StatusPill'),
        const Wrap(
          spacing: AppSpacing.xs,
          runSpacing: AppSpacing.xs,
          children: <Widget>[
            StatusPill(
                label: 'AI-generated · Unverified',
                variant: StatusPillVariant.aiGenerated,
                icon: 'sparkles'),
            StatusPill(
                label: 'Doctor approved',
                variant: StatusPillVariant.approved,
                icon: 'badgeCheck'),
            StatusPill(label: 'Review', variant: StatusPillVariant.needsReview),
            StatusPill(
                label: 'Conflict',
                variant: StatusPillVariant.conflict,
                icon: 'alertTriangle'),
            StatusPill(label: 'Demo data', variant: StatusPillVariant.demo),
            StatusPill(label: 'Neutral', variant: StatusPillVariant.neutral),
          ],
        ),
        const _Section('ConfidenceBadge'),
        const Wrap(
          spacing: AppSpacing.xs,
          runSpacing: AppSpacing.xs,
          children: <Widget>[
            ConfidenceBadge(band: ConfidenceBand.high, score: 0.95),
            ConfidenceBadge(band: ConfidenceBand.medium, score: 0.71),
            ConfidenceBadge(
                band: ConfidenceBand.needsVerification, score: 0.44),
          ],
        ),
        const _Section('ProgressRing · ProgressBar · AvatarStack'),
        Row(
          children: <Widget>[
            ProgressRing(
              progress: 0.87,
              child: Icon(AppIcons.byName('badgeCheck'),
                  size: 22, color: AppColors.primary),
            ),
            const SizedBox(width: AppSpacing.md),
            const ProgressRing(
                progress: 0.42, stroke: 6, color: AppColors.warning),
            const SizedBox(width: AppSpacing.md),
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  ProgressBar(value: 0.7),
                  SizedBox(height: AppSpacing.xs),
                  ProgressBar(value: 0.35, color: AppColors.warning),
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.md),
        const AvatarStack(items: <String>['pill', 'testTube', 'notebook']),
        const _Section('AddRow · DashedDivider'),
        const Align(
          alignment: Alignment.centerLeft,
          child: AddRow(label: 'Add Record'),
        ),
        const SizedBox(height: AppSpacing.sm),
        const DashedDivider(),
        const _Section('PillTabs'),
        PillTabs(
          labels: const <String>[
            'Timeline',
            'Medications',
            'Investigations',
            'Issues'
          ],
          selectedIndex: 0,
          onChanged: (_) {},
        ),
        const _Section('PatientCard'),
        SizedBox(
          height: AppSpacing.patientCardHeight,
          child: ListView(
            scrollDirection: Axis.horizontal,
            children: const <Widget>[
              PatientCard(
                  name: 'Demo Patient', subtitle: '52 yrs', monogram: 'DP'),
              SizedBox(width: AppSpacing.carouselGap),
              PatientCard(
                  name: 'Eleanor Vance', subtitle: '38 yrs', monogram: 'EV'),
              SizedBox(width: AppSpacing.carouselGap),
              PatientCard(
                  name: 'Add a patient',
                  subtitle: 'Tap to create',
                  monogram: '+'),
            ],
          ),
        ),
        const _Section('QuickActionTile · AIBanner'),
        const Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: <Widget>[
            QuickActionTile(iconName: 'fileUp', label: 'Upload\nRecord'),
            QuickActionTile(iconName: 'camera', label: 'Scan\nDocument'),
            QuickActionTile(iconName: 'mic', label: 'Voice\nNote'),
            QuickActionTile(
                iconName: 'fileText', label: 'Doctor\nBrief', selected: true),
          ],
        ),
        const SizedBox(height: AppSpacing.md),
        const AIBanner(
          title: 'Let AI prepare your consultation',
          subtitle: 'Evidence-linked. Reviewed by you. Verified on approval.',
        ),
        const _Section('TopBar · HeaderBlock'),
        const TopBar(title: 'Patient Overview', subtitle: 'Demo patient'),
        const SizedBox(height: AppSpacing.sm),
        const HeaderBlock(
          name: 'Demo Patient',
          metaLine: '52 yrs • Diabetology • 3d ago',
          documentTypeIcons: <String>[
            'fileText',
            'pill',
            'testTube',
            'notebook'
          ],
          documentOverflow: 6,
          chips: <Widget>[
            StatusPill(
                label: 'Active patient',
                variant: StatusPillVariant.approved,
                dense: true),
            StatusPill(
                label: '6 records',
                variant: StatusPillVariant.neutral,
                dense: true),
          ],
        ),
        const _Section('InsightCard · StatItem'),
        const InsightCard(
          title: 'Clinical Context Ready',
          metaLine1: 'Evidence-linked • Source-traceable',
          metaLine2: 'Unverified until approved',
          statusPill: StatusPill(
            label: '3 open',
            variant: StatusPillVariant.conflict,
            icon: 'alertTriangle',
            dense: true,
          ),
          stats: <Widget>[
            StatItem(iconName: 'files', label: 'Documents', value: '6'),
            StatItem(
                iconName: 'sparkles', label: 'Clinical Facts', value: '24'),
            StatItem(
                iconName: 'alertTriangle', label: 'Open Issues', value: '3'),
          ],
        ),
        const _Section('TimelineRail · TimelineCard'),
        const DatedTimelineEntry(
          date: '2026-09-28T16:30:00',
          child: TimelineCard(
            iconName: 'flaskConical',
            title: 'Lab: HbA1c',
            bullet1: 'HbA1c: 7.8 % (Ref: 4.0 – 5.6 %)',
            bullet2: '1 evidence-backed fact',
            onChevronTap: _noop,
            thumbnailIcon: 'testTube',
          ),
        ),
        const SizedBox(height: AppSpacing.sm),
        const Align(
          alignment: Alignment.centerLeft,
          child: AddRow(label: 'Add Activity'),
        ),
        const _Section('StickyActionBar'),
        const StickyActionBar(
          primaryLabel: 'Generate Brief',
          primaryIcon: 'sparkles',
          onPrimary: _noop,
          secondaryIcon: 'sliders',
          onSecondary: _noop,
        ),
        const _Section('TicketCard'),
        const TicketCard(
          headerLabel: 'MEDICATION CHANGE',
          statusLabel: 'Conflict',
          headerIconName: 'pill',
          connectorIconName: 'replace',
          connectorCaption: 'Changed',
          leftBlock: TicketRouteBlock(
              label: 'Source A', code: 'BD', time: '500 mg', date: '12 Sep'),
          rightBlock: TicketRouteBlock(
              label: 'Source B',
              code: 'BD',
              time: '1000 mg',
              date: '12 Sep',
              alignEnd: true),
          keyValues: <Widget>[
            KeyValueCell(label: 'Drug', value: 'Metformin'),
            KeyValueCell(label: 'Strength', value: '500 mg'),
            KeyValueCell(label: 'Records', value: '3'),
          ],
          trailingTile: EvidenceTile(),
        ),
        const _Section('LinkRowCard'),
        const LinkRowCard(
          title: 'Kayon Resort-style source row',
          label: 'Prescription',
          meta: '12 Sep 2026 • PDF',
          thumbnailIcon: 'pill',
          onTap: _noop,
        ),
        const _Section('MetricCard · ProgressRingCard'),
        const Row(
          children: <Widget>[
            Expanded(
              child: MetricCard(
                title: 'HbA1c',
                value: '7.8',
                unit: '%',
                caption1: 'High',
                caption2: '4.0 – 5.6 %',
                iconName: 'flaskConical',
                accent: AppColors.warning,
              ),
            ),
            SizedBox(width: AppSpacing.xs),
            Expanded(
              child: ProgressRingCard(
                title: 'Trip Progress',
                progress: 0.87,
                valueLabel: '87%',
                caption: 'Completed',
                glyph: 'shieldCheck',
              ),
            ),
          ],
        ),
        const _Section('ChecklistCard'),
        ChecklistCard(
          title: 'Packing Checklist',
          countLabel: '2 of 3 packed',
          items: const <ChecklistItemModel>[
            ChecklistItemModel(id: 'a', label: 'Travel Documents', done: true),
            ChecklistItemModel(id: 'b', label: 'Camera', done: true),
            ChecklistItemModel(id: 'c', label: 'Swimwear'),
          ],
          onItemToggle: (_, __) {},
        ),
        const _Section('BottomNav'),
        BottomNav(
          items: kShellTabs,
          activeIndex: 2,
          onSelected: (_) {},
        ),
        const _Section('EvidenceCard'),
        const EvidenceCard(
          sourceTitle: 'doc5_prescription_sep2026.pdf',
          sourceMeta: 'Prescription • 12 Sep 2026',
          pageChip: 'Page 1',
          verbatim:
              'Tab. Metformin 1000 mg twice daily (BD) indicated in second outpatient voucher.',
          highlight: 'Metformin 1000 mg twice daily (BD)',
          confidenceBand: ConfidenceBand.high,
          confidence: 0.95,
          provenanceVerified: true,
        ),
        const SizedBox(height: AppSpacing.md),
        const EvidenceCard(
          sourceTitle: 'scan_2026.png',
          sourceMeta: 'Imaging report • 3 Feb 2026',
          verbatim: null,
          confidenceBand: ConfidenceBand.needsVerification,
          confidence: 0.42,
        ),
        const _Section('States'),
        const SkeletonCard(height: 110),
        const SizedBox(height: AppSpacing.sm),
        const EmptyState(
          icon: 'files',
          title: 'No records yet',
          message:
              'Upload a PDF or scan a document — ClinSync reads it and links every claim back to its source.',
          actionLabel: 'Upload a record',
        ),
        const SizedBox(height: AppSpacing.sm),
        const ErrorStateView(
          message: 'Can\'t reach the server. Check your connection.',
          onRetry: _noop,
        ),
        const ClinicalDisclaimer(),
      ],
    );
  }

  static void _noop() {}
}

class _Shell extends StatelessWidget {
  const _Shell(
      {required this.title, required this.subtitle, required this.children});

  final String title;
  final String subtitle;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bgCanvas,
      body: SafeArea(
        child: Column(
          children: <Widget>[
            TopBar(
                title: title,
                subtitle: subtitle,
                onLeadingTap: () => context.pop()),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.screenH,
                  AppSpacing.md,
                  AppSpacing.screenH,
                  AppSpacing.xxxl,
                ),
                children: children,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Section extends StatelessWidget {
  const _Section(this.title);

  final String title;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: AppSpacing.lg, bottom: AppSpacing.xs),
      child: Row(
        children: <Widget>[
          Text(title, style: AppTypography.titleSection),
          const SizedBox(width: AppSpacing.xs),
          Expanded(child: Container(height: 1, color: AppColors.divider)),
        ],
      ),
    );
  }
}
