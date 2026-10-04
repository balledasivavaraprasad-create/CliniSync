import 'package:flutter/foundation.dart';

/// Runtime configuration — plan §0.2 rule 7: **never hardcode** the API base
/// URL, keys or demo flags. Use a config layer.
///
/// Resolution order (highest first):
///  1. Value persisted at runtime (Home → menu sheet) via `shared_preferences`.
///  2. `--dart-define=CLINSYNC_API_BASE_URL=…`
///  3. Platform-aware default (Android emulator → 10.0.2.2, else 127.0.0.1).
abstract final class AppConfig {
  const AppConfig._();

  static const String _defineBaseUrl =
      String.fromEnvironment('CLINSYNC_API_BASE_URL');
  static const bool _defineDemoMode =
      bool.fromEnvironment('CLINSYNC_DEMO_MODE');

  static const String prefBaseUrl = 'clinsync.base_url';
  static const String prefDemoMode = 'clinsync.demo_mode';
  static const String prefSpecialty = 'clinsync.specialty';
  static const String prefActivePatient = 'clinsync.active_patient';

  static const String defaultPort = '8000';
  static const String defaultHost = '127.0.0.1';
  static const String androidEmulatorHost = '10.0.2.2';

  static const String apiPrefix = '/api/v1';

  static String _baseUrlOverride = '';

  static bool get demoModeFromDefine => _defineDemoMode;
  static String get baseUrlFromDefine => _defineBaseUrl;

  static void applyBaseUrl(String value) {
    _baseUrlOverride = normalise(value);
  }

  /// The platform-aware default origin, e.g. `http://10.0.2.2:8000`.
  static String get defaultOrigin {
    if (_defineBaseUrl.isNotEmpty) return normalise(_defineBaseUrl);
    if (kIsWeb) return normalise('http://localhost:$defaultPort');
    switch (defaultTargetPlatform) {
      case TargetPlatform.android:
        return normalise('http://$androidEmulatorHost:$defaultPort');
      case TargetPlatform.iOS:
      case TargetPlatform.macOS:
      case TargetPlatform.fuchsia:
      case TargetPlatform.linux:
      case TargetPlatform.windows:
        return normalise('http://$defaultHost:$defaultPort');
    }
  }

  /// Effective base URL for [ApiClient]: origin + `/api/v1`.
  static String get baseUrl {
    final String originValue =
        _baseUrlOverride.isNotEmpty ? _baseUrlOverride : defaultOrigin;
    return '$originValue$apiPrefix';
  }

  static String get origin {
    final String url = baseUrl;
    return url.endsWith(apiPrefix)
        ? url.substring(0, url.length - apiPrefix.length)
        : url;
  }

  /// Strips trailing slashes and a trailing `/api/v1`.
  static String normalise(String raw) {
    String v = raw.trim();
    if (v.isEmpty) return '';
    if (v.endsWith(apiPrefix)) v = v.substring(0, v.length - apiPrefix.length);
    while (v.endsWith('/')) {
      v = v.substring(0, v.length - 1);
    }
    return v;
  }

  /// Accepts `host`, `host:port` or a full URL and returns a usable origin.
  static String withScheme(String raw) {
    String v = normalise(raw);
    if (v.isEmpty) return '';
    if (!v.startsWith('http://') && !v.startsWith('https://')) v = 'http://$v';
    return v;
  }

  /// LAN hints shown in the settings sheet (plan §10).
  static const List<({String label, String value})> baseUrlHints =
      <({String label, String value})>[
    (label: 'Android emulator', value: 'http://10.0.2.2:8000'),
    (label: 'iOS simulator', value: 'http://127.0.0.1:8000'),
    (label: 'Physical device (LAN)', value: 'http://192.168.1.10:8000'),
  ];
}
