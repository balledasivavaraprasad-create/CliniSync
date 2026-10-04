/// Error → human text map — plan §11.4.
///
/// Raw backend exceptions must never reach the UI (plan §6.6 rule 7).
abstract final class ErrorMessages {
  const ErrorMessages._();

  static const String unknown = 'Something went wrong.';
  static const String network =
      'Can\'t reach the server. Check your connection.';
  static const String timeout =
      'The server took too long to respond. Try again.';

  static const Map<String, String> _byCode = <String, String>{
    'DOCUMENT_PROCESSING_FAILED':
        'We couldn\'t read this document. Try a clearer scan.',
    'OCR_FAILED': 'We couldn\'t read this document. Try a clearer scan.',
    'EXTRACTION_FAILED':
        'We couldn\'t read the clinical details in this document. Try a clearer scan.',
    'LLM_UNAVAILABLE':
        'AI is temporarily unavailable. Showing the last available information.',
    'STT_FAILED': 'We couldn\'t transcribe that recording.',
    'GATE1_BLOCKED': 'Approval is on hold: some items need your review.',
    'GATE2_BLOCKED':
        'This summary needs another pass. Try generating it again.',
    'CONSULTATION_NOT_APPROVABLE': 'This consultation cannot be approved yet.',
    'INVALID_STATE_TRANSITION':
        'This consultation has already been approved and is locked.',
    'UNSUPPORTED_FILE_TYPE':
        'That file type is not supported. Upload a PDF or an image.',
    'FILE_TOO_LARGE': 'That file is too large. The limit is 25 MB.',
    'DUPLICATE_DOCUMENT':
        'That record has already been uploaded for this patient.',
    'NOT_FOUND': 'We couldn\'t find that record.',
    'VALIDATION_ERROR':
        'Some details look incomplete. Check the highlighted fields.',
    'NETWORK': network,
    'CONNECTION_ERROR': network,
    'TIMEOUT': timeout,
    'CANCELLED': 'That request was cancelled.',
    'MALFORMED_ENVELOPE': 'The server sent an unexpected response.',
    'HTTP_ERROR': unknown,
    'INTERNAL_ERROR': unknown,
  };

  /// Human text for a backend (or client-side) error code.
  static String forCode(String? code) {
    if (code == null || code.isEmpty) return unknown;
    return _byCode[code.toUpperCase()] ?? unknown;
  }
}
