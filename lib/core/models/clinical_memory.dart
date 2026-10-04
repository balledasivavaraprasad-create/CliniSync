import '../constants/enums.dart';
import '../utils/confidence_band.dart';
import '../utils/date_format.dart';
import 'json_utils.dart';

/// One row of `GET /patients/{id}/memory`.
class ClinicalMemoryItem {
  const ClinicalMemoryItem({
    required this.id,
    required this.memoryType,
    required this.content,
    this.sourceConsultationId,
    this.verified = true,
    this.validationReportId,
    this.createdAt,
  });

  factory ClinicalMemoryItem.fromJson(Map<String, dynamic> json) {
    return ClinicalMemoryItem(
      id: asStringOr(json['id'], ''),
      memoryType: MemoryType.fromWire(json['memory_type']),
      content: MemoryContent.fromJson(asMap(json['content'])),
      sourceConsultationId: asString(json['source_consultation_id']),
      verified: asBool(json['verified'], fallback: true),
      validationReportId: asString(json['validation_report_id']),
      createdAt: json['created_at'],
    );
  }

  final String id;
  final MemoryType memoryType;

  /// `content` is a nested object whose shape depends on [memoryType].
  final MemoryContent content;
  final String? sourceConsultationId;
  final bool verified;
  final String? validationReportId;
  final Object? createdAt;

  String get approvedLabel => AppDate.date(createdAt);

  /// `Type 2 Diabetes Mellitus · active · onset 2026-01-10`
  String get summaryLine => content.summary;
}

/// Tolerant reader for `clinical_memory.content`.
class MemoryContent {
  const MemoryContent(this.fields);

  factory MemoryContent.fromJson(Map<String, dynamic> json) =>
      MemoryContent(Map<String, dynamic>.from(json));

  final Map<String, dynamic> fields;

  bool get isEmpty => fields.isEmpty;

  String get headline {
    if (fields.isEmpty) return 'No detail recorded';
    for (final key in const <String>[
      'diagnosis',
      'assessment',
      'plan',
      'note',
      'text'
    ]) {
      final v = asString(fields[key]);
      if (v != null) return v;
    }
    final active = asList(fields['active_regimen']);
    if (active.isNotEmpty) {
      return active.map((dynamic e) => e.toString()).join(' · ');
    }
    return fields.entries.first.value.toString();
  }

  String get summary => fields.entries.map((MapEntry<String, dynamic> e) {
        final v = e.value;
        final text = v is List
            ? v.map((dynamic x) => x.toString()).join(', ')
            : v.toString();
        return '${_humanise(e.key)}: $text';
      }).join(' · ');

  /// Bullet lines for the memory card body.
  List<String> get bullets {
    if (fields.isEmpty) return const <String>[];
    final out = <String>[];
    fields.forEach((dynamic key, dynamic v) {
      if (v is List) {
        for (final item in v) {
          final s = item.toString().trim();
          if (s.isNotEmpty) out.add('${_humanise(key)}: $s');
        }
      } else if (v is Map) {
        v.forEach((dynamic k, dynamic inner) {
          final s = inner is List ? inner.join(', ') : inner.toString();
          if (s.trim().isNotEmpty) {
            out.add('${_humanise(key)} ${_humanise(k)}: $s');
          }
        });
      } else {
        final s = v.toString().trim();
        if (s.isNotEmpty) out.add('${_humanise(key)}: $s');
      }
    });
    return out;
  }

  static String _humanise(String key) {
    final words = key.replaceAll(RegExp(r'[_\-]+'), ' ').trim();
    if (words.isEmpty) return key;
    return '${words[0].toUpperCase()}${words.substring(1)}';
  }
}

/// `POST /patients/{id}/voice` → voice note with proposed facts.
class VoiceNote {
  const VoiceNote({
    required this.id,
    this.transcriptRaw,
    this.transcriptNormalized,
    this.sttModel,
    this.sttConfidence,
    this.reviewStatus,
    this.proposedFacts = const <VoiceProposedFact>[],
  });

  factory VoiceNote.fromJson(Map<String, dynamic> json) {
    final conf = asDouble(json['stt_confidence']);
    return VoiceNote(
      id: asStringOr(json['id'], ''),
      transcriptRaw: asString(json['transcript_raw']),
      transcriptNormalized: asString(json['transcript_normalized']),
      sttModel: asString(json['stt_model']),
      sttConfidence: conf,
      reviewStatus: asString(json['review_status']),
      proposedFacts: asMapList(json['proposed_facts'])
          .map(VoiceProposedFact.fromJson)
          .toList(growable: false),
    );
  }

  final String id;
  final String? transcriptRaw;
  final String? transcriptNormalized;
  final String? sttModel;
  final double? sttConfidence;
  final String? reviewStatus;
  final List<VoiceProposedFact> proposedFacts;

  /// The backend falls back to a placeholder transcript when STT fails.
  bool get usedFallback => sttModel == 'fallback';

  String get transcript => (transcriptNormalized ?? '').trim().isNotEmpty
      ? transcriptNormalized!.trim()
      : (transcriptRaw ?? '').trim();

  ConfidenceBand get confidenceBand => ConfidenceBand.fromValue(sttConfidence);
}

/// A fact proposed by a voice note — always `needs_verification`.
class VoiceProposedFact {
  const VoiceProposedFact({
    required this.id,
    required this.factType,
    required this.value,
    this.confidenceBand = ConfidenceBand.needsVerification,
    this.verificationStatus = VerificationStatus.needsVerification,
    this.sourceText,
  });

  factory VoiceProposedFact.fromJson(Map<String, dynamic> json) {
    return VoiceProposedFact(
      id: asStringOr(json['id'], ''),
      factType: FactType.fromWire(json['fact_type']),
      value: asStringOr(json['value'], ''),
      confidenceBand: ConfidenceBand.fromWire(json['confidence_band']),
      verificationStatus:
          VerificationStatus.fromWire(json['verification_status']),
      sourceText: asString(json['source_text']),
    );
  }

  final String id;
  final FactType factType;
  final String value;
  final ConfidenceBand confidenceBand;
  final VerificationStatus verificationStatus;
  final String? sourceText;
}

/// `POST /voice/{id}/review`.
class VoiceReviewResult {
  const VoiceReviewResult({
    required this.id,
    required this.reviewStatus,
    this.transcriptNormalized,
    this.promotedFacts = 0,
  });

  factory VoiceReviewResult.fromJson(Map<String, dynamic> json) {
    return VoiceReviewResult(
      id: asStringOr(json['id'], ''),
      reviewStatus: asStringOr(json['review_status'], 'reviewed'),
      transcriptNormalized: asString(json['transcript_normalized']),
      promotedFacts: asIntOr(json['promoted_facts'], 0),
    );
  }

  final String id;
  final String reviewStatus;
  final String? transcriptNormalized;
  final int promotedFacts;
}
