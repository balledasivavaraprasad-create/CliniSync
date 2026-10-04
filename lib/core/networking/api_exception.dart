/// Typed API failure — plan §11.4. Raw backend exceptions are never shown.
class ApiException implements Exception {
  const ApiException({
    required this.code,
    required this.message,
    this.statusCode,
    this.details,
    this.isNetwork = false,
  });

  /// Backend error code (`NOT_FOUND`, `GATE1_BLOCKED`, …) or a synthetic
  /// client-side code (`NETWORK`, `TIMEOUT`, `MALFORMED_ENVELOPE`, …).
  final String code;

  /// Human-facing text. Never a raw exception.
  final String message;

  final int? statusCode;
  final Map<String, dynamic>? details;
  final bool isNetwork;

  @override
  String toString() => 'ApiException($code, $message)';
}
