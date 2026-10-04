import '../constants/enums.dart';
import 'json_utils.dart';

/// `DocumentResponse`.
class ClinicalDocument {
  const ClinicalDocument({
    required this.id,
    required this.patientId,
    required this.originalFilename,
    this.mimeType,
    this.fileSize = 0,
    this.pageCount = 0,
    this.documentType = RecordType.unknown,
    this.documentDate,
    this.classificationConfidence,
    this.processingStatus = ProcessingStatus.uploaded,
    this.processingErrorCode,
    this.ocrMethod,
    this.isFallback = false,
    this.uploadedVia,
    this.createdAt,
    this.duplicate = false,
  });

  factory ClinicalDocument.fromJson(Map<String, dynamic> json) {
    return ClinicalDocument(
      id: asStringOr(json['id'], ''),
      patientId: asStringOr(json['patient_id'], ''),
      originalFilename:
          asStringOr(json['original_filename'], 'Untitled record'),
      mimeType: asString(json['mime_type']),
      fileSize: asIntOr(json['file_size'], 0),
      pageCount: asIntOr(json['page_count'], 0),
      documentType: RecordType.fromWire(json['document_type']),
      documentDate: json['document_date'],
      classificationConfidence: asDouble(json['classification_confidence']),
      processingStatus: ProcessingStatus.fromWire(json['processing_status']),
      processingErrorCode: asString(json['processing_error_code']),
      ocrMethod: asString(json['ocr_method']),
      isFallback: asBool(json['is_fallback']),
      uploadedVia: asString(json['uploaded_via']),
      createdAt: json['created_at'],
      duplicate: asBool(json['duplicate']),
    );
  }

  final String id;
  final String patientId;
  final String originalFilename;
  final String? mimeType;
  final int fileSize;
  final int pageCount;
  final RecordType documentType;
  final Object? documentDate;

  /// Confidence of the *classification* step.
  final double? classificationConfidence;
  final ProcessingStatus processingStatus;
  final String? processingErrorCode;
  final String? ocrMethod;

  /// True when OCR fell back — surfaced as a subtle `Demo data`-style tag.
  final bool isFallback;
  final String? uploadedVia;
  final Object? createdAt;

  /// Backend returned an already-stored document for a repeated upload.
  final bool duplicate;

  bool get isProcessed => processingStatus == ProcessingStatus.complete;
  bool get needsReview => processingStatus == ProcessingStatus.needsReview;
  bool get isFailed => processingStatus == ProcessingStatus.failed;
  bool get canProcess => !processingStatus.isTerminal;

  String get sizeLabel {
    if (fileSize <= 0) return '—';
    if (fileSize < 1024) return '$fileSize B';
    if (fileSize < 1024 * 1024) return '${(fileSize / 1024).round()} KB';
    return '${(fileSize / (1024 * 1024)).toStringAsFixed(1)} MB';
  }

  /// Title shown on document cards: filename without extension, tidied.
  String get displayName {
    final raw = originalFilename;
    final dot = raw.lastIndexOf('.');
    final stem = dot > 0 ? raw.substring(0, dot) : raw;
    return stem.replaceAll(RegExp(r'[_\-]+'), ' ').trim();
  }
}

/// `DocumentPageResponse` — `GET /documents/{id}/pages/{n}`.
class DocumentPage {
  const DocumentPage({
    required this.pageNumber,
    required this.text,
    this.ocrConfidence,
    this.method,
  });

  factory DocumentPage.fromJson(Map<String, dynamic> json) {
    return DocumentPage(
      pageNumber: asIntOr(json['page_number'], 1),
      text: asStringOr(json['text'], ''),
      ocrConfidence: asDouble(json['ocr_confidence']),
      method: asString(json['method']),
    );
  }

  final int pageNumber;
  final String text;
  final double? ocrConfidence;
  final String? method;
}

/// One stage of `GET /documents/{id}/status`.
class PipelineStageState {
  const PipelineStageState({
    required this.name,
    required this.label,
    required this.completed,
  });

  factory PipelineStageState.fromJson(Map<String, dynamic> json) {
    return PipelineStageState(
      name: asStringOr(json['name'], ''),
      label: asStringOr(json['label'], ''),
      completed: asBool(json['completed']),
    );
  }

  final String name;
  final String label;
  final bool completed;

  PipelineStage get stage => PipelineStage.fromWire(name);
}

/// `GET /documents/{id}/status`.
class ProcessingStatusSnapshot {
  const ProcessingStatusSnapshot({
    required this.documentId,
    required this.status,
    this.currentStage,
    this.stages = const <PipelineStageState>[],
    this.errorCode,
  });

  factory ProcessingStatusSnapshot.fromJson(Map<String, dynamic> json) {
    return ProcessingStatusSnapshot(
      documentId: asStringOr(json['document_id'], ''),
      status: ProcessingStatus.fromWire(json['status']),
      currentStage: asString(json['current_stage']),
      stages: asMapList(json['stages'])
          .map(PipelineStageState.fromJson)
          .toList(growable: false),
      errorCode: asString(json['error_code']),
    );
  }

  final String documentId;
  final ProcessingStatus status;
  final String? currentStage;
  final List<PipelineStageState> stages;
  final String? errorCode;

  bool get isTerminal => status.isTerminal;

  /// 0..1 for the progress ring.
  double get progress {
    if (stages.isEmpty) {
      return switch (status) {
        ProcessingStatus.uploaded => 0.08,
        ProcessingStatus.extractingText => 0.25,
        ProcessingStatus.classifying => 0.42,
        ProcessingStatus.extractingEntities => 0.62,
        ProcessingStatus.normalizing => 0.80,
        ProcessingStatus.validating => 0.90,
        ProcessingStatus.complete => 1,
        ProcessingStatus.needsReview => 1,
        ProcessingStatus.failed => 1,
      };
    }
    final done = stages.where((PipelineStageState s) => s.completed).length;
    return (done / stages.length).clamp(0.0, 1.0);
  }
}
