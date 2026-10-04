import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/animations/motion.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_radii.dart';
import '../../core/theme/app_shadows.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../widgets/app_icons.dart';

/// Which bottom-nav tab is active — driven by `go_router`'s current location.
class ShellTab {
  const ShellTab(
      {required this.label,
      required this.iconName,
      required this.activeIconName});

  final String label;

  /// Thin-stroke line icon.
  final String iconName;

  /// Filled icon used for the active state.
  final String activeIconName;
}

/// Floating white bar, r 28, `shadowFloat`, 4 items: 24 px line icon + 11 px
/// label; active = `primary` filled icon + `primary` label; inactive =
/// `textTertiary` — plan §7.6.
class BottomNav extends StatelessWidget {
  const BottomNav({
    super.key,
    required this.items,
    required this.activeIndex,
    required this.onSelected,
  });

  final List<ShellTab> items;
  final int activeIndex;
  final ValueChanged<int> onSelected;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: EdgeInsets.fromLTRB(
        AppSpacing.md,
        0,
        AppSpacing.md,
        MediaQuery.paddingOf(context).bottom + AppSpacing.xs,
      ),
      padding:
          const EdgeInsets.symmetric(horizontal: AppSpacing.xs, vertical: 10),
      decoration: const BoxDecoration(
        color: AppColors.surface,
        borderRadius: AppRadii.allXl,
        boxShadow: AppShadows.float,
      ),
      child: Row(
        children: <Widget>[
          for (int i = 0; i < items.length; i++)
            Expanded(
              child: PressScale(
                onTap: () => onSelected(i),
                scale: 0.94,
                child: _NavItem(
                  item: items[i],
                  active: i == activeIndex,
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  const _NavItem({required this.item, required this.active});

  final ShellTab item;
  final bool active;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        AnimatedContainer(
          duration: const Duration(milliseconds: 220),
          curve: Curves.easeOutCubic,
          width: 34,
          height: 26,
          decoration: BoxDecoration(
            color: active ? AppColors.primarySoft : Colors.transparent,
            borderRadius: AppRadii.allPill,
          ),
          alignment: Alignment.center,
          child: Icon(
            AppIcons.byName(active ? item.activeIconName : item.iconName),
            size: 20,
            color: active ? AppColors.primary : AppColors.textTertiary,
          ),
        ),
        const SizedBox(height: 3),
        Text(
          item.label,
          style: AppTypography.navLabel.copyWith(
            color: active ? AppColors.primary : AppColors.textTertiary,
            fontWeight: active ? FontWeight.w600 : FontWeight.w500,
          ),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
      ],
    );
  }
}

/// The 4 tab destinations — plan §6.4 nav mapping
/// (`Home / Patients / Records / Memory`).
const List<ShellTab> kShellTabs = <ShellTab>[
  ShellTab(label: 'Home', iconName: 'home', activeIconName: 'home'),
  ShellTab(label: 'Patients', iconName: 'users', activeIconName: 'users'),
  ShellTab(label: 'Records', iconName: 'files', activeIconName: 'files'),
  ShellTab(
      label: 'Memory', iconName: 'bookMarked', activeIconName: 'bookMarked'),
];

/// The `ShellRoute` scaffold: canvas + floating bottom nav.
class AppShell extends StatelessWidget {
  const AppShell({super.key, required this.child, required this.location});

  final Widget child;
  final String location;

  int get _activeIndex {
    if (location.startsWith('/patients')) return 1;
    if (location.startsWith('/records')) return 2;
    if (location.startsWith('/memory')) return 3;
    return 0;
  }

  void _go(BuildContext context, int index) {
    switch (index) {
      case 0:
        context.go('/home');
      case 1:
        context.go('/patients');
      case 2:
        context.go('/records');
      case 3:
        context.go('/memory');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bgCanvas,
      extendBody: true,
      body: child,
      bottomNavigationBar: BottomNav(
        items: kShellTabs,
        activeIndex: _activeIndex,
        onSelected: (int i) => _go(context, i),
      ),
    );
  }
}
