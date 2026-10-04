import 'dart:convert';

import 'package:flutter/foundation.dart' show visibleForTesting;
import 'package:flutter/services.dart' show rootBundle;

/// Reads the bundled offline fixtures — plan §14 fallback tier 4.
///
/// Only used when the backend is unreachable **and** Demo mode is on. Values
/// carry `meta.source == "fallback"` so the UI can label them `Demo data`
/// (plan §6.6 rule 8).
abstract final class DemoStore {
  const DemoStore._();

  static final Map<String, dynamic> _cache = <String, dynamic>{};

  static bool contains(String assetPath) =>
      _cache.containsKey(assetPath) || true;

  static Future<Map<String, dynamic>?> envelope(String assetPath) async {
    final cached = _cache[assetPath];
    if (cached != null) return cached;
    try {
      final raw = await rootBundle.loadString(assetPath);
      final decoded = jsonDecode(raw);
      if (decoded is! Map) return null;
      final map = Map<String, dynamic>.from(decoded);
      final meta = map['meta'] is Map
          ? Map<String, dynamic>.from(map['meta'] as Map)
          : <String, dynamic>{};
      meta['source'] = 'fallback';
      meta['request_id'] = 'req_demo_bundle';
      map['meta'] = meta;
      _cache[assetPath] = map;
      return map;
    } catch (_) {
      return null;
    }
  }

  static Future<List<dynamic>> dataList(String assetPath) async {
    final env = await envelope(assetPath);
    final data = env?['data'];
    if (data is List) return data;
    return const <dynamic>[];
  }

  static Future<Map<String, dynamic>?> dataMap(String assetPath) async {
    final env = await envelope(assetPath);
    final data = env?['data'];
    if (data is Map) return Map<String, dynamic>.from(data);
    return null;
  }

  @visibleForTesting
  static void clearCache() => _cache.clear();
}
