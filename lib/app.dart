import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/repositories/providers.dart';
import 'core/theme/app_theme.dart';
import 'shared/navigation/app_router.dart';

/// Root widget — `MaterialApp.router`, theme, global providers (plan §8).
///
/// No login, no authentication, no profile screens (plan §0.2 rule 4).
class ClinSyncApp extends ConsumerWidget {
  const ClinSyncApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp.router(
      title: 'ClinSync',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      routerConfig: appRouter,
      builder: (BuildContext context, Widget? child) {
        // Clamp text scaling so the reference layout never overflows, while
        // still honouring the user's accessibility preference.
        final MediaQueryData mq = MediaQuery.of(context);
        return MediaQuery(
          data: mq.copyWith(
            textScaler:
                mq.textScaler.clamp(minScaleFactor: 0.9, maxScaleFactor: 1.25),
          ),
          child: child ?? const SizedBox.shrink(),
        );
      },
    );
  }
}

/// Convenience wrapper that supplies the `shared_preferences` override.
class ClinSyncAppRoot extends StatelessWidget {
  const ClinSyncAppRoot({super.key, required this.preferences});

  final dynamic preferences;

  @override
  Widget build(BuildContext context) {
    return ProviderScope(
      overrides: <Override>[
        sharedPreferencesProvider.overrideWithValue(preferences)
      ],
      child: const AnnotatedRegion<SystemUiOverlayStyle>(
        value: SystemUiOverlayStyle(
          statusBarColor: Colors.transparent,
          statusBarIconBrightness: Brightness.dark,
          statusBarBrightness: Brightness.light,
          systemNavigationBarColor: Color(0xFFF6F6F4),
          systemNavigationBarIconBrightness: Brightness.dark,
        ),
        child: ClinSyncApp(),
      ),
    );
  }
}
