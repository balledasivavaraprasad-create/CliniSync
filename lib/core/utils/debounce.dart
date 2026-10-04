import 'dart:async';

/// Debounce helper for search fields — plan §9.1 / §9.2.
class Debouncer {
  Debouncer({this.milliseconds = 320});

  final int milliseconds;
  Timer? _timer;

  void call(void Function() action) {
    _timer?.cancel();
    _timer = Timer(Duration(milliseconds: milliseconds), action);
  }

  void dispose() {
    _timer?.cancel();
    _timer = null;
  }
}

/// Human-readable byte size for document rows.
String formatBytes(int bytes) {
  if (bytes <= 0) return '—';
  if (bytes < 1024) return '$bytes B';
  if (bytes < 1024 * 1024) return '${(bytes / 1024).round()} KB';
  return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
}

/// "Metformin 500 mg" → "Metformin"; "hba1c" → "Hba1c".
String titleCaseWords(String value) {
  if (value.isEmpty) return value;
  return value
      .split(RegExp(r'[\s_\-]+'))
      .where((String p) => p.isNotEmpty)
      .map((String p) => '${p[0].toUpperCase()}${p.substring(1)}')
      .join(' ');
}
