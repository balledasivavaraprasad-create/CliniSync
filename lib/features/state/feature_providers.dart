import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/constants/enums.dart';
import '../../core/models/clinical_fact.dart';
import '../../core/models/clinical_memory.dart';
import '../../core/models/consultation.dart';
import '../../core/models/doctor_brief.dart';
import '../../core/models/document.dart';
import '../../core/models/investigation.dart';
import '../../core/models/json_utils.dart';
import '../../core/models/medication.dart';
import '../../core/models/patient.dart';
import '../../core/models/timeline_event.dart';
import '../../core/networking/api_exception.dart';
import '../../core/repositories/clinical_repository.dart';
import '../../core/repositories/providers.dart';
import '../../core/utils/confidence_band.dart';

/// A generic loadable slice: loading / data / error with a manual `refresh()`
/// (plan §11.3).
@immutable
class AsyncSlice<T> {
  const AsyncSlice({
    this.data,
    this.loading = false,
    this.error,
    this.isDemo = false,
  });

  final T? data;
  final bool loading;
  final ApiException? error;

  /// True when the value came from the bundled offline fixtures.
  final bool isDemo;

  bool get hasData => data != null;
  bool get hasError => error != null && !loading;

  AsyncSlice<T> copyWith({
    T? data,
    bool? loading,
    ApiException? error,
    bool? isDemo,
    bool clearError = false,
    bool clearData = false,
  }) {
    return AsyncSlice<T>(
      data: clearData ? null : (data ?? this.data),
      loading: loading ?? this.loading,
      error: clearError ? null : (error ?? this.error),
      isDemo: isDemo ?? this.isDemo,
    );
  }
}

ApiException asApiException(Object error) {
  if (error is ApiException) return error;
  return const ApiException(code: 'UNKNOWN', message: 'Something went wrong.');
}

// ═══════════════════════════════════════════════════════════════════════════
// Home / Patients
// ═══════════════════════════════════════════════════════════════════════════

/// `GET /patients?limit=6` — Home carousel and the shell `Patients` tab.
class PatientsNotifier extends StateNotifier<AsyncSlice<List<Patient>>> {
  PatientsNotifier(this._ref) : super(const AsyncSlice<List<Patient>>()) {
    load();
  }

  final Ref _ref;

  Future<void> load({String? query}) async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final List<Patient> patients = await _ref
          .read(patientRepositoryProvider)
          .list(limit: 50, query: query);
      state = AsyncSlice<List<Patient>>(data: patients, loading: false);
    } catch (e) {
      state = state.copyWith(loading: false, error: asApiException(e));
    }
  }

  Future<void> refresh() => load();

  /// Optimistic local filter so typing feels instant (plan §9.1).
  List<Patient> filtered(String query) {
    final List<Patient>? all = state.data;
    if (all == null) return const <Patient>[];
    final String q = query.trim().toLowerCase();
    if (q.isEmpty) return all;
    return all
        .where((Patient p) =>
            p.fullName.toLowerCase().contains(q) ||
            (p.ageLabel.toLowerCase().contains(q)) ||
            (p.sexLabel.toLowerCase().contains(q)))
        .toList(growable: false);
  }

  Future<Patient> create({
    required String fullName,
    String? dateOfBirth,
    int? ageYears,
    String? sex,
    String? contactRef,
  }) async {
    final Patient created = await _ref.read(patientRepositoryProvider).create(
          PatientCreate(
            fullName: fullName,
            dateOfBirth: dateOfBirth,
            ageYears: ageYears,
            sex: sex,
            contactRef: contactRef,
          ),
        );
    await load();
    return created;
  }
}

final patientsProvider =
    StateNotifierProvider<PatientsNotifier, AsyncSlice<List<Patient>>>(
        PatientsNotifier.new);

// ═══════════════════════════════════════════════════════════════════════════
// Patient overview
// ═══════════════════════════════════════════════════════════════════════════

class OverviewNotifier extends StateNotifier<AsyncSlice<PatientOverview>> {
  OverviewNotifier(this._ref, this._patientId)
      : super(const AsyncSlice<PatientOverview>()) {
    load();
  }

  final Ref _ref;
  final String _patientId;

  Future<void> load() async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final PatientOverview overview =
          await _ref.read(patientRepositoryProvider).overview(_patientId);
      state = AsyncSlice<PatientOverview>(data: overview);
    } catch (e) {
      state = state.copyWith(loading: false, error: asApiException(e));
    }
  }

  Future<void> refresh() => load();
}

final overviewProvider = StateNotifierProvider.family<OverviewNotifier,
    AsyncSlice<PatientOverview>, String>(
  OverviewNotifier.new,
);

// ═══════════════════════════════════════════════════════════════════════════
// Documents
// ═══════════════════════════════════════════════════════════════════════════

class DocumentsNotifier
    extends StateNotifier<AsyncSlice<List<ClinicalDocument>>> {
  DocumentsNotifier(this._ref, this._patientId)
      : super(const AsyncSlice<List<ClinicalDocument>>()) {
    load();
  }

  final Ref _ref;
  final String _patientId;

  Future<void> load() async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final List<ClinicalDocument> docs =
          await _ref.read(documentRepositoryProvider).list(_patientId);
      state = AsyncSlice<List<ClinicalDocument>>(data: docs);
    } catch (e) {
      state = state.copyWith(loading: false, error: asApiException(e));
    }
  }

  Future<void> refresh() => load();

  /// Upload then auto-kick the pipeline (plan §9.4).
  Future<ClinicalDocument> upload(
    File file, {
    required String uploadedVia,
    void Function(int sent, int total)? onProgress,
  }) async {
    final ClinicalDocument doc =
        await _ref.read(documentRepositoryProvider).upload(
              _patientId,
              file,
              uploadedVia: uploadedVia,
              onProgress: onProgress,
            );
    await _ref.read(documentRepositoryProvider).process(doc.id);
    await load();
    return doc;
  }

  Future<void> process(ClinicalDocument doc) async {
    await _ref.read(documentRepositoryProvider).process(doc.id);
    await load();
  }

  Future<void> reprocess(ClinicalDocument doc) async {
    await _ref.read(documentRepositoryProvider).reprocess(doc.id);
    await load();
  }

  List<ClinicalDocument> filteredBy(RecordType? type) {
    final List<ClinicalDocument>? all = state.data;
    if (all == null) return const <ClinicalDocument>[];
    if (type == null) return all;
    return all
        .where((ClinicalDocument d) => d.documentType == type)
        .toList(growable: false);
  }
}

final documentsProvider = StateNotifierProvider.family<DocumentsNotifier,
    AsyncSlice<List<ClinicalDocument>>, String>(
  DocumentsNotifier.new,
);

// ═══════════════════════════════════════════════════════════════════════════
// Processing status (polled)
// ═══════════════════════════════════════════════════════════════════════════

class ProcessingNotifier
    extends StateNotifier<AsyncSlice<ProcessingStatusSnapshot>> {
  ProcessingNotifier(this._ref, this._documentId)
      : super(const AsyncSlice<ProcessingStatusSnapshot>()) {
    load();
  }

  final Ref _ref;
  final String _documentId;
  Timer? _timer;

  Future<void> load() async {
    try {
      final ProcessingStatusSnapshot snap =
          await _ref.read(documentRepositoryProvider).status(_documentId);
      state = AsyncSlice<ProcessingStatusSnapshot>(data: snap);
      _schedule();
    } catch (e) {
      state = state.copyWith(loading: false, error: asApiException(e));
      // Fall back to staged client-side progress so the screen still advances
      // (plan §9.5).
      _schedule();
    }
  }

  /// Poll every 1.5 s until a terminal state (plan §9.5).
  void _schedule() {
    _timer?.cancel();
    final ProcessingStatusSnapshot? snap = state.data;
    final bool terminal = snap?.isTerminal ?? false;
    if (terminal) return;
    _timer = Timer.periodic(const Duration(milliseconds: 1500), (_) => load());
  }

  Future<void> retry() => load();

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }
}

final processingProvider = StateNotifierProvider.family<ProcessingNotifier,
    AsyncSlice<ProcessingStatusSnapshot>, String>(
  ProcessingNotifier.new,
);

// ═══════════════════════════════════════════════════════════════════════════
// Timeline
// ═══════════════════════════════════════════════════════════════════════════

class TimelineNotifier extends StateNotifier<AsyncSlice<List<TimelineEvent>>> {
  TimelineNotifier(this._ref, this._patientId)
      : super(const AsyncSlice<List<TimelineEvent>>()) {
    load();
  }

  final Ref _ref;
  final String _patientId;

  Future<void> load({String? type}) async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final List<TimelineEvent> events = await _ref
          .read(timelineRepositoryProvider)
          .list(_patientId, type: type, limit: 100);
      state = AsyncSlice<List<TimelineEvent>>(data: events);
    } catch (e) {
      state = state.copyWith(loading: false, error: asApiException(e));
    }
  }

  Future<void> refresh() => load();

  /// Dated events, newest first; undated ones are grouped at the end.
  List<TimelineEvent> get dated => (state.data ?? const <TimelineEvent>[])
      .where((TimelineEvent e) => !e.isUndated)
      .toList();

  List<TimelineEvent> get undated => (state.data ?? const <TimelineEvent>[])
      .where((TimelineEvent e) => e.isUndated)
      .toList();
}

final timelineProvider = StateNotifierProvider.family<TimelineNotifier,
    AsyncSlice<List<TimelineEvent>>, String>(
  TimelineNotifier.new,
);

// ═══════════════════════════════════════════════════════════════════════════
// Medications
// ═══════════════════════════════════════════════════════════════════════════

class MedicationsNotifier extends StateNotifier<AsyncSlice<List<Medication>>> {
  MedicationsNotifier(this._ref, this._patientId)
      : super(const AsyncSlice<List<Medication>>()) {
    load();
  }

  final Ref _ref;
  final String _patientId;

  Future<void> load() async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final List<Medication> meds =
          await _ref.read(medicationRepositoryProvider).list(_patientId);
      state = AsyncSlice<List<Medication>>(data: meds);
    } catch (e) {
      state = state.copyWith(loading: false, error: asApiException(e));
    }
  }

  Future<void> refresh() => load();

  List<Medication> byStatus(MedicationStatus status) =>
      (state.data ?? const <Medication>[])
          .where((Medication m) => m.status == status)
          .toList(growable: false);

  List<Medication> get conflicts => (state.data ?? const <Medication>[])
      .where((Medication m) => m.hasConflict)
      .toList(growable: false);
}

final medicationsProvider = StateNotifierProvider.family<MedicationsNotifier,
    AsyncSlice<List<Medication>>, String>(
  MedicationsNotifier.new,
);

/// `GET /patients/{id}/medications/{group_key}/history` — plan §9.9.
final medicationHistoryProvider = FutureProvider.autoDispose.family<
    List<MedicationHistoryEntry>, ({String patientId, String groupKey})>(
  (Ref ref, ({String patientId, String groupKey}) args) {
    return ref
        .read(medicationRepositoryProvider)
        .history(args.patientId, args.groupKey);
  },
);

// ═══════════════════════════════════════════════════════════════════════════
// Investigations
// ═══════════════════════════════════════════════════════════════════════════

class InvestigationsNotifier
    extends StateNotifier<AsyncSlice<List<Investigation>>> {
  InvestigationsNotifier(this._ref, this._patientId)
      : super(const AsyncSlice<List<Investigation>>()) {
    load();
  }

  final Ref _ref;
  final String _patientId;

  Future<void> load() async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final List<Investigation> inv =
          await _ref.read(investigationRepositoryProvider).list(_patientId);
      state = AsyncSlice<List<Investigation>>(data: inv);
    } catch (e) {
      state = state.copyWith(loading: false, error: asApiException(e));
    }
  }

  Future<void> refresh() => load();
}

final investigationsProvider = StateNotifierProvider.family<
    InvestigationsNotifier, AsyncSlice<List<Investigation>>, String>(
  InvestigationsNotifier.new,
);

/// `GET /patients/{id}/investigations/{group_key}/trend` — plan §9.11.
final investigationTrendProvider = FutureProvider.autoDispose
    .family<InvestigationTrend, ({String patientId, String groupKey})>(
  (Ref ref, ({String patientId, String groupKey}) args) {
    return ref
        .read(investigationRepositoryProvider)
        .trend(args.patientId, args.groupKey);
  },
);

// ═══════════════════════════════════════════════════════════════════════════
// Issues
// ═══════════════════════════════════════════════════════════════════════════

class IssuesNotifier extends StateNotifier<AsyncSlice<List<ClinicalIssue>>> {
  IssuesNotifier(this._ref, this._patientId)
      : super(const AsyncSlice<List<ClinicalIssue>>()) {
    load();
  }

  final Ref _ref;
  final String _patientId;

  Future<void> load() async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final List<ClinicalIssue> issues =
          await _ref.read(issueRepositoryProvider).list(_patientId);
      state = AsyncSlice<List<ClinicalIssue>>(data: issues);
    } catch (e) {
      state = state.copyWith(loading: false, error: asApiException(e));
    }
  }

  Future<void> refresh() => load();

  /// Acknowledge / dismiss. The backend accepts any string; only `open` is ever
  /// written by it, so the UI keeps the local value optimistic.
  Future<void> patch(ClinicalIssue issue, IssueStatus status) async {
    final List<ClinicalIssue>? all = state.data;
    if (all != null) {
      state = AsyncSlice<List<ClinicalIssue>>(
        data: all
            .map((ClinicalIssue i) =>
                i.id == issue.id ? _withStatus(i, status) : i)
            .toList(growable: false),
      );
    }
    try {
      await _ref
          .read(issueRepositoryProvider)
          .patch(issue.id, status: status.wire);
    } catch (e) {
      await load();
      rethrow;
    }
  }

  Future<void> recompute() async {
    await _ref.read(issueRepositoryProvider).recompute(_patientId);
    await load();
  }

  List<ClinicalIssue> get open => (state.data ?? const <ClinicalIssue>[])
      .where((ClinicalIssue i) => i.isOpen)
      .toList();

  List<ClinicalIssue> get conflicts =>
      open.where((ClinicalIssue i) => i.isConflict).toList();

  List<ClinicalIssue> get missing =>
      open.where((ClinicalIssue i) => i.isMissingInfo).toList();

  List<ClinicalIssue> get lowConfidence => open
      .where((ClinicalIssue i) => i.issueType == IssueType.lowConfidenceFact)
      .toList(growable: false);

  int get reviewedCount => (state.data ?? const <ClinicalIssue>[])
      .where((ClinicalIssue i) => !i.isOpen)
      .length;

  /// Issues linked to a medication — drives the reconciliation entry point.
  ClinicalIssue? conflictFor(String canonicalName) {
    final String needle = canonicalName.toLowerCase();
    for (final ClinicalIssue i in open) {
      final String haystack = <String>[
        i.title,
        i.description ?? '',
        i.drug ?? ''
      ].join(' ').toLowerCase();
      if (haystack.contains(needle)) return i;
    }
    return null;
  }
}

/// Rebuilds an issue with a new status, preserving every other field.
ClinicalIssue _withStatus(ClinicalIssue issue, IssueStatus status) {
  return ClinicalIssue(
    id: issue.id,
    title: issue.title,
    issueType: issue.issueType,
    severity: issue.severity,
    description: issue.description,
    relatedDocumentIds: issue.relatedDocumentIds,
    relatedFactIds: issue.relatedFactIds,
    detail: issue.detail,
    status: status,
    doctorNote: issue.doctorNote,
    createdAt: issue.createdAt,
    updatedAt: issue.updatedAt,
  );
}

final issuesProvider = StateNotifierProvider.family<IssuesNotifier,
    AsyncSlice<List<ClinicalIssue>>, String>(
  IssuesNotifier.new,
);

// ═══════════════════════════════════════════════════════════════════════════
// Facts
// ═══════════════════════════════════════════════════════════════════════════

class FactsNotifier extends StateNotifier<AsyncSlice<List<ClinicalFact>>> {
  FactsNotifier(this._ref, this._patientId)
      : super(const AsyncSlice<List<ClinicalFact>>()) {
    load();
  }

  final Ref _ref;
  final String _patientId;

  Future<void> load({FactTypeFilter? type, VerificationFilter? status}) async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final List<ClinicalFact> facts = await _ref
          .read(factRepositoryProvider)
          .list(_patientId, type: type, status: status);
      state = AsyncSlice<List<ClinicalFact>>(data: facts);
    } catch (e) {
      state = state.copyWith(loading: false, error: asApiException(e));
    }
  }

  Future<void> refresh() => load();

  List<ClinicalFact> filtered(FactTypeFilter type, VerificationFilter status) {
    final List<ClinicalFact>? all = state.data;
    if (all == null) return const <ClinicalFact>[];
    return all.where((ClinicalFact f) {
      final bool typeOk =
          type == FactTypeFilter.all || f.factType.wire == type.name;
      final bool statusOk = status == VerificationFilter.all ||
          f.verificationStatus.wire == status.wire;
      return typeOk && statusOk;
    }).toList(growable: false);
  }

  Future<void> verify(ClinicalFact fact, {required bool verified}) async {
    await _ref.read(factRepositoryProvider).verify(
          fact.id,
          verificationStatus: verified
              ? VerificationStatus.doctorVerified.wire
              : VerificationStatus.needsVerification.wire,
        );
    await load();
  }
}

final factsProvider = StateNotifierProvider.family<FactsNotifier,
    AsyncSlice<List<ClinicalFact>>, String>(
  FactsNotifier.new,
);

// ═══════════════════════════════════════════════════════════════════════════
// Brief
// ═══════════════════════════════════════════════════════════════════════════

/// Staged loading messages — plan §9.15.
enum BriefStage {
  idle('Preparing'),
  collecting('Collecting evidence'),
  comparing('Comparing records'),
  preparing('Preparing brief');

  const BriefStage(this.label);
  final String label;
}

class BriefNotifier extends StateNotifier<AsyncSlice<DoctorBrief>> {
  BriefNotifier(this._ref, this._patientId)
      : super(const AsyncSlice<DoctorBrief>(loading: true)) {
    load();
  }

  final Ref _ref;
  final String _patientId;

  BriefStage stage = BriefStage.idle;
  String? specialty;
  bool isDemo = false;
  DoctorBrief? lastBrief;

  Future<void> load({bool force = false}) async {
    state = state.copyWith(loading: true, clearError: true);
    stage = BriefStage.collecting;
    _emit();
    try {
      final DoctorBrief brief = specialty == null
          ? await _ref.read(briefRepositoryProvider).latest(_patientId)
          : await _ref.read(briefRepositoryProvider).generate(
                _patientId,
                specialty: specialty!,
                forceRegenerate: force,
              );
      stage = BriefStage.preparing;
      lastBrief = brief;
      state = AsyncSlice<DoctorBrief>(data: brief, isDemo: isDemo);
      stage = BriefStage.idle;
    } catch (e) {
      state = state.copyWith(loading: false, error: asApiException(e));
      stage = BriefStage.idle;
    }
  }

  void _emit() {
    // Re-publish so the staged message is visible while loading.
    state = state.copyWith(loading: true);
  }

  Future<void> refresh() => load(force: true);
}

final briefProvider = StateNotifierProvider.family<BriefNotifier,
    AsyncSlice<DoctorBrief>, String>(
  BriefNotifier.new,
);

// ═══════════════════════════════════════════════════════════════════════════
// Consultations
// ═══════════════════════════════════════════════════════════════════════════

class ConsultationNotifier extends StateNotifier<AsyncSlice<Consultation>> {
  ConsultationNotifier(this._ref, this._patientId, this._consultationId)
      : super(const AsyncSlice<Consultation>(loading: true)) {
    if (_consultationId.isNotEmpty) load();
  }

  final Ref _ref;
  final String _patientId;
  final String _consultationId;

  /// True once a consultation (or a freshly created draft) has been loaded.
  bool get hasLoaded => _loaded;

  bool _loaded = false;

  /// Working copy; `dirty` drives the unsaved-changes guard (plan §9.15).
  ConsultationContent? draft;
  bool dirty = false;
  bool saving = false;

  Future<void> load() async {
    if (_consultationId.isEmpty) return;
    try {
      final Consultation c =
          await _ref.read(consultationRepositoryProvider).byId(_consultationId);
      draft = c.currentVersion?.content?.copy();
      _loaded = true;
      state = AsyncSlice<Consultation>(data: c);
    } catch (e) {
      state = state.copyWith(loading: false, error: asApiException(e));
    }
  }

  /// Create a fresh AI draft from the brief.
  Future<Consultation> createDraft(
      {String specialty = 'general_medicine', String? briefId}) async {
    saving = true;
    try {
      final Consultation c = await _ref
          .read(consultationRepositoryProvider)
          .create(_patientId, specialty: specialty, briefId: briefId);
      draft = c.currentVersion?.content?.copy();
      _loaded = true;
      dirty = false;
      state = AsyncSlice<Consultation>(data: c);
      return c;
    } finally {
      saving = false;
    }
  }

  /// `POST /consultations/{id}/versions` — a new version row.
  Future<void> saveVersion({String? changeSummary}) async {
    final ConsultationContent? content = draft;
    if (content == null) return;
    saving = true;
    try {
      await _ref.read(consultationRepositoryProvider).createVersion(
          _consultationId, content,
          changeSummary: changeSummary);
      dirty = false;
      await load();
    } finally {
      saving = false;
    }
  }

  /// `PUT /consultations/{id}` — edits the current version in place.
  Future<void> saveInPlace() async {
    final ConsultationContent? content = draft;
    if (content == null) return;
    saving = true;
    try {
      await _ref
          .read(consultationRepositoryProvider)
          .update(_consultationId, content);
      dirty = false;
      await load();
    } finally {
      saving = false;
    }
  }

  void update(ConsultationSection section, String value) {
    draft ??= ConsultationContent();
    draft!.setText(section, value);
    dirty = true;
    // Trigger a rebuild without another network call.
    state = state.copyWith();
  }
}

final consultationProvider = StateNotifierProvider.autoDispose.family<
    ConsultationNotifier,
    AsyncSlice<Consultation>,
    ({String patientId, String consultationId})>(
  (Ref ref, ({String patientId, String consultationId}) args) =>
      ConsultationNotifier(ref, args.patientId, args.consultationId),
);

/// `GET /consultations/{id}/versions` — plan §9.16.
final consultationVersionsProvider =
    FutureProvider.autoDispose.family<List<ConsultationVersion>, String>(
  (Ref ref, String consultationId) =>
      ref.read(consultationRepositoryProvider).versions(consultationId),
);

/// `POST /consultations/{id}/approve/preview` — plan §9.17.
final approvalPreviewProvider = FutureProvider.autoDispose
    .family<ApprovalPreview, ({String consultationId, bool acknowledged})>(
  (Ref ref, ({String consultationId, bool acknowledged}) args) {
    return ref.read(consultationRepositoryProvider).approvalPreview(
        args.consultationId,
        acknowledgedUnedited: args.acknowledged);
  },
);

// ═══════════════════════════════════════════════════════════════════════════
// Clinical memory
// ═══════════════════════════════════════════════════════════════════════════

class MemoryNotifier
    extends StateNotifier<AsyncSlice<List<ClinicalMemoryItem>>> {
  MemoryNotifier(this._ref, this._patientId)
      : super(const AsyncSlice<List<ClinicalMemoryItem>>()) {
    load();
  }

  final Ref _ref;
  final String _patientId;

  Future<void> load() async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final List<ClinicalMemoryItem> memory =
          await _ref.read(memoryRepositoryProvider).verified(_patientId);
      state = AsyncSlice<List<ClinicalMemoryItem>>(data: memory);
    } catch (e) {
      state = state.copyWith(loading: false, error: asApiException(e));
    }
  }

  Future<void> refresh() => load();

  List<ClinicalMemoryItem> byType(MemoryType? type) {
    final List<ClinicalMemoryItem>? all = state.data;
    if (all == null) return const <ClinicalMemoryItem>[];
    if (type == null) return all;
    return all
        .where((ClinicalMemoryItem m) => m.memoryType == type)
        .toList(growable: false);
  }
}

final memoryProvider = StateNotifierProvider.family<MemoryNotifier,
    AsyncSlice<List<ClinicalMemoryItem>>, String>(
  MemoryNotifier.new,
);

final memoryHistoryProvider =
    FutureProvider.autoDispose.family<List<ClinicalMemoryItem>, String>(
  (Ref ref, String patientId) =>
      ref.read(memoryRepositoryProvider).history(patientId),
);

// ═══════════════════════════════════════════════════════════════════════════
// Evidence
// ═══════════════════════════════════════════════════════════════════════════

/// `GET /facts/{id}/evidence` — plan §9.6.
final evidenceProvider =
    FutureProvider.autoDispose.family<FactEvidence, String>(
  (Ref ref, String factId) => ref.read(factRepositoryProvider).evidence(factId),
);

// ═══════════════════════════════════════════════════════════════════════════
// Specialty
// ═══════════════════════════════════════════════════════════════════════════

/// The chosen specialty, persisted per install and sent with the brief request.
class SpecialtyController extends StateNotifier<Specialty> {
  SpecialtyController(this._prefs)
      : super(Specialty.fromWire(_prefs.getString(prefKey)));

  final dynamic _prefs;
  static const String prefKey = 'clinsync.specialty';

  Future<void> select(Specialty value) async {
    state = value;
    await _prefs.setString(prefKey, value.wire);
  }
}

final specialtyProvider = StateNotifierProvider<SpecialtyController, Specialty>(
  (Ref ref) => SpecialtyController(ref.watch(sharedPreferencesProvider)),
);

/// Types referenced from `shared/loading/states.dart` and screens.
typedef ConfidenceBandT = ConfidenceBand;

/// Helper used by the Overview stat strip.
int countOf<T>(Iterable<T> items, bool Function(T) test) =>
    items.where(test).length;

/// Reads a raw map field defensively; used where the backend shape is unclear.
Object? pick(Map<String, dynamic> json, String key) => asMap(json)[key];

/// Strongly-typed alias so screens do not import `json_utils` directly.
typedef JsonMap = Map<String, dynamic>;
