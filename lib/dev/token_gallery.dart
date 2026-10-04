import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/app_radii.dart';
import '../core/theme/app_shadows.dart';
import '../core/theme/app_spacing.dart';
import '../core/theme/app_typography.dart';
import '../shared/widgets/primitives.dart';

/// `TokenGallery` — task C06 acceptance. Shows every §7.1–§7.5 token so drift is
/// visible next to the reference image.
class TokenGallery extends StatelessWidget {
  const TokenGallery({super.key});

  @override
  Widget build(BuildContext context) {
    return _GalleryShell(
      title: 'Token gallery',
      subtitle: 'Colour · type · spacing · radii · shadow',
      children: <Widget>[
        const _Section('Colour'),
        const Wrap(
          spacing: AppSpacing.xs,
          runSpacing: AppSpacing.xs,
          children: <Widget>[
            _Swatch('bgBackdrop', AppColors.bgBackdrop),
            _Swatch('bgCanvas', AppColors.bgCanvas),
            _Swatch('surface', AppColors.surface),
            _Swatch('surfaceTint', AppColors.surfaceTint),
            _Swatch('primary', AppColors.primary),
            _Swatch('primaryDark', AppColors.primaryDark),
            _Swatch('primaryMuted', AppColors.primaryMuted),
            _Swatch('primarySoft', AppColors.primarySoft),
            _Swatch('textPrimary', AppColors.textPrimary),
            _Swatch('textSecondary', AppColors.textSecondary),
            _Swatch('textTertiary', AppColors.textTertiary),
            _Swatch('divider', AppColors.divider),
            _Swatch('warning', AppColors.warning),
            _Swatch('danger', AppColors.danger),
          ],
        ),
        const _Section('Gradients'),
        const Row(
          children: <Widget>[
            Expanded(child: _GradientCard('photoScrim', AppColors.photoScrim)),
            SizedBox(width: AppSpacing.xs),
            Expanded(child: _GradientCard('heroFade', AppColors.heroFade)),
          ],
        ),
        const SizedBox(height: AppSpacing.xs),
        const Row(
          children: <Widget>[
            Expanded(child: _GradientCard('banner', AppColors.banner)),
            SizedBox(width: AppSpacing.xs),
            Expanded(child: _GradientCard('monogram', AppColors.monogram)),
          ],
        ),
        const _Section('Typography'),
        for (final (String name, TextStyle style) in _styles)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.xs),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                SizedBox(
                  width: 108,
                  child: Text(
                    name,
                    style: AppTypography.caption
                        .copyWith(color: AppColors.textTertiary),
                  ),
                ),
                Expanded(
                    child: Text('Every Record, Clinically Connected.',
                        style: style)),
              ],
            ),
          ),
        const _Section('Spacing (4-pt grid)'),
        const Wrap(
          spacing: AppSpacing.xs,
          runSpacing: AppSpacing.xs,
          children: <Widget>[
            _Chip('4', AppSpacing.xxs),
            _Chip('8', AppSpacing.xs),
            _Chip('12', AppSpacing.sm),
            _Chip('16', AppSpacing.md),
            _Chip('20', AppSpacing.lg),
            _Chip('24', AppSpacing.xl),
            _Chip('32', AppSpacing.xxl),
            _Chip('40', AppSpacing.xxxl),
          ],
        ),
        const _Section('Radii'),
        const Row(
          children: <Widget>[
            _RadiusCard('sm 12', AppRadii.sm),
            SizedBox(width: AppSpacing.xs),
            _RadiusCard('md 16', AppRadii.md),
            SizedBox(width: AppSpacing.xs),
            _RadiusCard('lg 22', AppRadii.lg),
            SizedBox(width: AppSpacing.xs),
            _RadiusCard('xl 28', AppRadii.xl),
            SizedBox(width: AppSpacing.xs),
            _RadiusCard('pill', AppRadii.pill),
          ],
        ),
        const _Section('Shadows'),
        const Row(
          children: <Widget>[
            _ShadowCard('shadowCard', AppShadows.card),
            SizedBox(width: AppSpacing.xs),
            _ShadowCard('shadowFloat', AppShadows.float),
            SizedBox(width: AppSpacing.xs),
            _ShadowCard('shadowButton', AppShadows.button),
          ],
        ),
      ],
    );
  }

  static final List<(String, TextStyle)> _styles = <(String, TextStyle)>[
    ('displayHero', AppTypography.displayHero),
    ('displayHero accent', AppTypography.displayHeroAccent),
    ('titleScreen', AppTypography.titleScreen),
    ('titleHeader', AppTypography.titleHeader),
    ('titleSection', AppTypography.titleSection),
    ('titleCard', AppTypography.titleCard),
    ('body', AppTypography.body),
    ('bodyBullet', AppTypography.bodyBullet),
    ('label', AppTypography.label),
    ('caption', AppTypography.caption),
    ('capsLabel', AppTypography.capsLabel),
    ('numberLarge', AppTypography.numberLarge),
    ('numberStat', AppTypography.numberStat),
    ('button', AppTypography.button),
    ('link', AppTypography.link),
    ('verbatim', AppTypography.verbatim),
  ];
}

class _GalleryShell extends StatelessWidget {
  const _GalleryShell(
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
      child: Text(title, style: AppTypography.titleSection),
    );
  }
}

class _Swatch extends StatelessWidget {
  const _Swatch(this.name, this.color);

  final String name;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final bool light = color.computeLuminance() > 0.5;
    return SizedBox(
      width: 104,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Container(
            height: 46,
            decoration: BoxDecoration(
              color: color,
              borderRadius: AppRadii.allMd,
              border: Border.all(color: AppColors.divider),
            ),
          ),
          const SizedBox(height: 3),
          Text(
            name,
            style: AppTypography.caption.copyWith(
              fontSize: 9.5,
              color: light ? AppColors.textPrimary : AppColors.textSecondary,
            ),
          ),
          Text(
            '#${color.toARGB32().toRadixString(16).substring(2).toUpperCase()}',
            style: AppTypography.caption
                .copyWith(fontSize: 9, color: AppColors.textTertiary),
          ),
        ],
      ),
    );
  }
}

class _GradientCard extends StatelessWidget {
  const _GradientCard(this.name, this.gradient);

  final String name;
  final Gradient gradient;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 62,
      decoration: BoxDecoration(
        gradient: gradient,
        borderRadius: AppRadii.allMd,
        border: Border.all(color: AppColors.divider),
      ),
      alignment: Alignment.bottomLeft,
      padding: const EdgeInsets.all(6),
      child: Text(name, style: AppTypography.caption.copyWith(fontSize: 9)),
    );
  }
}

class _Chip extends StatelessWidget {
  const _Chip(this.label, this.size);

  final String label;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size + AppSpacing.md,
      height: size + AppSpacing.md,
      decoration: const BoxDecoration(
        color: AppColors.primarySoft,
        borderRadius: AppRadii.allSm,
      ),
      alignment: Alignment.center,
      child: Text(label,
          style: AppTypography.caption.copyWith(color: AppColors.primaryDark)),
    );
  }
}

class _RadiusCard extends StatelessWidget {
  const _RadiusCard(this.label, this.radius);

  final String label;
  final double radius;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        children: <Widget>[
          Container(
            height: 54,
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(radius),
              boxShadow: AppShadows.card,
            ),
          ),
          const SizedBox(height: 3),
          Text(label, style: AppTypography.caption.copyWith(fontSize: 9)),
        ],
      ),
    );
  }
}

class _ShadowCard extends StatelessWidget {
  const _ShadowCard(this.label, this.shadows);

  final String label;
  final List<BoxShadow> shadows;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        children: <Widget>[
          Container(
            height: 54,
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: AppRadii.allMd,
              boxShadow: shadows,
            ),
          ),
          const SizedBox(height: 3),
          Text(label, style: AppTypography.caption.copyWith(fontSize: 9)),
        ],
      ),
    );
  }
}
