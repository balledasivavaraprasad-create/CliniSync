import '../../core/constants/enums.dart';
import '../../core/utils/confidence_band.dart';
import 'json_utils.dart';

/// One row of `GET /patients/{id}/facts`.
class ClinicalFact {
  const ClinicalFact({
    required this.id,
    required this.factType,
    required this.value,
    this.patientId,
    this.documentId,
    this.factDate,
    this.confidence,
    this.confidenceBand = ConfidenceBand.needsVerification,
    this.sourceText,
    this.sourcePage,
    this.provenanceVerified = false,
    this.verificationStatus = VerificationStatus.unverified,
    this.createdAt,
  });

  factory ClinicalFact.fromJson(Map<String, dynamic> json) {
    final confidence = asDouble(json['confidence']);
    return ClinicalFact(
      id: asStringOr(json['id'], ''),
      factType: FactType.fromWire(json['fact_type']),
      value: asStringOr(json['value'], ''),
      patientId: asString(json['patient_id']),
      documentId: asString(json['document_id']),
      factDate: json['fact_date'],
      confidence: confidence,
      confidenceBand: ConfidenceBand.fromWire(json['confidence_band'],
          confidence: confidence),
      sourceText: asString(json['source_text']),
      sourcePage: asInt(json['source_page']),
      provenanceVerified: asBool(json['provenance_verified']),
      verificationStatus:
          VerificationStatus.fromWire(json['verification_status']),
      createdAt: json['created_at'],
    );
  }

  final String id;
  final FactType factType;
  final String value;
  final String? patientId;
  final String? documentId;
  final Object? factDate;
  final double? confidence;
  final ConfidenceBand confidenceBand;
  final String? sourceText;
  final int? sourcePage;

  /// `true` when the verbatim span was found in the OCR page text.
  final bool provenanceVerified;
  final VerificationStatus verificationStatus;
  final Object? createdAt;

  bool get isVerified =>
      verificationStatus == VerificationStatus.doctorVerified;
  bool get needsVerification =>
      verificationStatus == VerificationStatus.needsVerification ||
      verificationStatus == VerificationStatus.unverified;

  String get confidenceLabel => confidenceBand.label;

  String get confidencePercent {
    final c = confidence;
    if (c == null) return '—';
    return '${(c * 100).round()}%';
  }

  String get pageChipLabel =>
      sourcePage == null ? 'Page —' : 'Page $sourcePage';
}

/// `source` block of `GET /facts/{id}/evidence`.
class EvidenceSource {
  const EvidenceSource({
    required this.documentId,
    required this.documentFilename,
    this.documentType = RecordType.unknown,
    this.documentDate,
    this.pageNumber,
    this.verbatimText,
    this.spanStart,
    this.spanEnd,
  });

  factory EvidenceSource.fromJson(Map<String, dynamic> json) {
    return EvidenceSource(
      documentId: asStringOr(json['document_id'], ''),
      documentFilename: asStringOr(json['document_filename'], 'Source record'),
      documentType: RecordType.fromWire(json['document_type']),
      documentDate: json['document_date'],
      pageNumber: asInt(json['page_number']),
      verbatimText: asString(json['verbatim_text']),
      spanStart: asInt(json['span_start']),
      spanEnd: asInt(json['span_end']),
    );
  }

  final String documentId;
  final String documentFilename;
  final RecordType documentType;
  final Object? documentDate;
  final int? pageNumber;
  final String? verbatimText;
  final int? spanStart;
  final int? spanEnd;

  bool get hasVerbatim => (verbatimText ?? '').isNotEmpty;

  String get pageChipLabel =>
      pageNumber == null ? 'Page —' : 'Page $pageNumber';
}

/// `GET /facts/{id}/evidence`.
class FactEvidence {
  const FactEvidence({
    required this.factId,
    required this.factType,
    required this.value,
    this.confidence,
    this.confidenceBand = ConfidenceBand.needsVerification,
    this.provenanceVerified = false,
    this.verificationStatus = VerificationStatus.unverified,
    required this.source,
  });

  factory FactEvidence.fromJson(Map<String, dynamic> json) {
    final confidence = asDouble(json['confidence']);
    return FactEvidence(
      factId: asStringOr(json['fact_id'], ''),
      factType: FactType.fromWire(json['fact_type']),
      value: asStringOr(json['value'], ''),
      confidence: confidence,
      confidenceBand: ConfidenceBand.fromWire(json['confidence_band'],
          confidence: confidence),
      provenanceVerified: asBool(json['provenance_verified']),
      verificationStatus:
          VerificationStatus.fromWire(json['verification_status']),
      source: EvidenceSource.fromJson(asMap(json['source'])),
    );
  }

  final String factId;
  final FactType factType;
  final String value;
  final double? confidence;
  final ConfidenceBand confidenceBand;
  final bool provenanceVerified;
  final VerificationStatus verificationStatus;
  final EvidenceSource source;
}

/// Result of `PATCH /facts/{id}`.
class FactVerificationResult {
  const FactVerificationResult({
    required this.id,
    this.value,
    this.verificationStatus = VerificationStatus.unverified,
  });

  factory FactVerificationResult.fromJson(Map<String, dynamic> json) {
    return FactVerificationResult(
      id: asStringOr(json['id'], ''),
      value: asString(json['value']),
      verificationStatus:
          VerificationStatus.fromWire(json['verification_status']),
    );
  }

  final String id;
  final String? value;
  final VerificationStatus verificationStatus;
}
