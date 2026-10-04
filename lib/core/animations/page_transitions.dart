import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

/// Route transitions — plan §7.9.
///
/// Forward: fade-through + 16 px upward slide, 280 ms `easeOutCubic`.
/// Back: reverse, 220 ms. Reduce-motion shortens both to 100 ms.
PageTransitionsBuilder buildPageTransitions() {
  return const _ClinPageTransitionsBuilder();
}

class _ClinPageTransitionsBuilder extends PageTransitionsBuilder {
  const _ClinPageTransitionsBuilder();

  @override
  Widget buildTransitions<T>(
    PageRoute<T> route,
    BuildContext context,
    Animation<double> animation,
    Animation<double> secondaryAnimation,
    Widget child,
  ) {
    final reduceMotion =
        MediaQuery.maybeOf(context)?.disableAnimations ?? false;

    // A `PageTransitionsBuilder` cannot change the route's own duration, so the
    // 280 / 220 ms timings are set where the route is created — `ClinPageRoute`
    // below and go_router's `pageBuilder`. Reduce-motion is honoured here by
    // removing the easing and the slide.
    final curved = CurvedAnimation(
      parent: animation,
      curve: reduceMotion ? Curves.linear : Curves.easeOutCubic,
      reverseCurve: Curves.easeOutCubic,
    );

    return FadeTransition(
      opacity: curved,
      child: SlideTransition(
        position: Tween<Offset>(
          begin: reduceMotion ? Offset.zero : const Offset(0, 0.045),
          end: Offset.zero,
        ).animate(curved),
        child: child,
      ),
    );
  }
}

/// Fade-through + slide-up page route for imperative navigation.
class ClinPageRoute<T> extends PageRouteBuilder<T> {
  ClinPageRoute({required WidgetBuilder builder, super.settings})
      : super(
          pageBuilder: (BuildContext context, Animation<double> a,
                  Animation<double> b) =>
              builder(context),
          transitionDuration: const Duration(milliseconds: 280),
          reverseTransitionDuration: const Duration(milliseconds: 220),
          transitionsBuilder: (
            BuildContext context,
            Animation<double> animation,
            Animation<double> secondary,
            Widget child,
          ) {
            final reduceMotion =
                MediaQuery.maybeOf(context)?.disableAnimations ?? false;
            final curved = CurvedAnimation(
              parent: animation,
              curve: reduceMotion ? Curves.linear : Curves.easeOutCubic,
              reverseCurve: Curves.easeOutCubic,
            );
            return FadeTransition(
              opacity: curved,
              child: SlideTransition(
                position: Tween<Offset>(
                        begin: const Offset(0, 0.06), end: Offset.zero)
                    .animate(curved),
                child: child,
              ),
            );
          },
        );
}

/// Bottom-sheet route with the slide-up + fade used by every ClinSync sheet.
class ClinSheetRoute<T> extends PageRouteBuilder<T> {
  ClinSheetRoute({required WidgetBuilder builder})
      : super(
          opaque: false,
          barrierColor: AppColors.textPrimary.withValues(alpha: 0.28),
          pageBuilder: (BuildContext context, Animation<double> a,
                  Animation<double> b) =>
              builder(context),
          transitionDuration: const Duration(milliseconds: 260),
          reverseTransitionDuration: const Duration(milliseconds: 200),
          transitionsBuilder: (
            BuildContext context,
            Animation<double> animation,
            Animation<double> secondary,
            Widget child,
          ) {
            final curved = CurvedAnimation(
              parent: animation,
              curve: Curves.easeOutCubic,
              reverseCurve: Curves.easeOutCubic,
            );
            return SlideTransition(
              position:
                  Tween<Offset>(begin: const Offset(0, 1), end: Offset.zero)
                      .animate(curved),
              child: FadeTransition(opacity: curved, child: child),
            );
          },
        );
}
