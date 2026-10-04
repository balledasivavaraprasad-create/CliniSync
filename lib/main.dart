import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'app.dart';

/// Entry point.
///
/// The runtime config layer (plan §7 hard rule 7) resolves the API base URL in
/// this order:
///   1. `--dart-define=CLINSYNC_API_BASE_URL=http://<host>:8000`
///   2. the platform default (Android emulator → `10.0.2.2`, else `127.0.0.1`)
///   3. a value persisted from the Home menu sheet at runtime
Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  await SystemChrome.setPreferredOrientations(<DeviceOrientation>[
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.dark,
    statusBarBrightness: Brightness.light,
  ));

  final SharedPreferences preferences = await SharedPreferences.getInstance();

  runApp(ClinSyncAppRoot(preferences: preferences));
}
