import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../config/app_config.dart';
import '../models/specialty.dart';
import '../models/user_account.dart';
import '../networking/api_client.dart';
import '../repositories/auth_repository.dart';
import '../repositories/brief_repository.dart';
import '../repositories/clinical_repository.dart';
import '../repositories/document_repository.dart';
import '../repositories/intelligence_repository.dart';
import '../repositories/patient_repository.dart';
import '../repositories/reference_repository.dart';

// ── Infrastructure ───────────────────────────────────────────────────────

final sharedPreferencesProvider = Provider<SharedPreferences>(
  (Ref ref) => throw UnimplementedError(
      'sharedPreferencesProvider must be overridden in main()'),
);

final apiClientProvider = Provider<ApiClient>((Ref ref) {
  // Rebuild when the persisted base URL changes so the client re-reads it.
  ref.watch(appSettingsProvider);
  return ApiClient();
});

// ── App settings ─────────────────────────────────────────────────────────

@immutable
class AppSettings {
  const AppSettings({
    required this.baseUrl,
    required this.demoMode,
    required this.specialty,
    required this.loaded,
  });

  final String baseUrl;

  /// When true and the backend is unreachable, repositories read bundled JSON.
  final bool demoMode;
  final String specialty;
  final bool loaded;

  static const AppSettings initial = AppSettings(
    baseUrl: '',
    demoMode: false,
    specialty: 'general_medicine',
    loaded: false,
  );

  AppSettings copyWith({
    String? baseUrl,
    bool? demoMode,
    String? specialty,
    bool? loaded,
  }) {
    return AppSettings(
      baseUrl: baseUrl ?? this.baseUrl,
      demoMode: demoMode ?? this.demoMode,
      specialty: specialty ?? this.specialty,
      loaded: loaded ?? this.loaded,
    );
  }
}

/// Runtime-configurable base URL, demo flag and specialty (plan §9.1 menu).
class AppSettingsController extends StateNotifier<AppSettings> {
  AppSettingsController(this._prefs) : super(AppSettings.initial) {
    _restore();
  }

  final SharedPreferences _prefs;

  Future<void> _restore() async {
    final storedBase = _prefs.getString(AppConfig.prefBaseUrl) ?? '';
    if (storedBase.isNotEmpty) AppConfig.applyBaseUrl(storedBase);
    final storedDemo =
        _prefs.getBool(AppConfig.prefDemoMode) ?? AppConfig.demoModeFromDefine;
    final storedSpecialty =
        _prefs.getString(AppConfig.prefSpecialty) ?? 'general_medicine';
    state = AppSettings(
      baseUrl: AppConfig.baseUrl,
      demoMode: storedDemo,
      specialty: storedSpecialty,
      loaded: true,
    );
  }

  Future<void> setBaseUrl(String raw) async {
    final normalised = AppConfig.withScheme(raw);
    AppConfig.applyBaseUrl(normalised);
    await _prefs.setString(AppConfig.prefBaseUrl, normalised);
    state = state.copyWith(baseUrl: AppConfig.baseUrl, loaded: true);
  }

  // ignore: avoid_positional_boolean_parameters — setter reads naturally as setDemoMode(x).
  Future<void> setDemoMode(bool value) async {
    await _prefs.setBool(AppConfig.prefDemoMode, value);
    state = state.copyWith(demoMode: value, loaded: true);
  }

  Future<void> setSpecialty(String wire) async {
    await _prefs.setString(AppConfig.prefSpecialty, wire);
    state = state.copyWith(specialty: wire, loaded: true);
  }
}

final appSettingsProvider =
    StateNotifierProvider<AppSettingsController, AppSettings>(
  (Ref ref) => AppSettingsController(ref.watch(sharedPreferencesProvider)),
);

// ── Active patient ───────────────────────────────────────────────────────

/// The patient the `Records` and `Memory` tabs operate on (plan §8).
class ActivePatientController extends StateNotifier<String?> {
  ActivePatientController(this._prefs)
      : super(_prefs.getString(AppConfig.prefActivePatient));

  final SharedPreferences _prefs;
  String? _pending;

  /// De-duplicates concurrent selections (Home carousel + list row taps).
  bool select(String? id) {
    if (_pending != null && _pending != id) return false;
    if (id == null) {
      state = null;
      _prefs.remove(AppConfig.prefActivePatient);
      return true;
    }
    _pending = id;
    state = id;
    _prefs.setString(AppConfig.prefActivePatient, id);
    scheduleMicrotask(() => _pending = null);
    return true;
  }

  void clear() => select(null);
}

final activePatientIdProvider =
    StateNotifierProvider<ActivePatientController, String?>(
  (Ref ref) => ActivePatientController(ref.watch(sharedPreferencesProvider)),
);

// ── Repositories ─────────────────────────────────────────────────────────

final patientRepositoryProvider = Provider<PatientRepository>(
  (Ref ref) => PatientRepository(ref.watch(apiClientProvider)),
);
final documentRepositoryProvider = Provider<DocumentRepository>(
  (Ref ref) => DocumentRepository(ref.watch(apiClientProvider)),
);
final factRepositoryProvider = Provider<FactRepository>(
  (Ref ref) => FactRepository(ref.watch(apiClientProvider)),
);
final medicationRepositoryProvider = Provider<MedicationRepository>(
  (Ref ref) => MedicationRepository(ref.watch(apiClientProvider)),
);
final timelineRepositoryProvider = Provider<TimelineRepository>(
  (Ref ref) => TimelineRepository(ref.watch(apiClientProvider)),
);
final investigationRepositoryProvider = Provider<InvestigationRepository>(
  (Ref ref) => InvestigationRepository(ref.watch(apiClientProvider)),
);
final issueRepositoryProvider = Provider<IssueRepository>(
  (Ref ref) => IssueRepository(ref.watch(apiClientProvider)),
);
final briefRepositoryProvider = Provider<BriefRepository>(
  (Ref ref) => BriefRepository(ref.watch(apiClientProvider)),
);
final consultationRepositoryProvider = Provider<ConsultationRepository>(
  (Ref ref) => ConsultationRepository(ref.watch(apiClientProvider)),
);
final memoryRepositoryProvider = Provider<MemoryRepository>(
  (Ref ref) => MemoryRepository(ref.watch(apiClientProvider)),
);
final voiceRepositoryProvider = Provider<VoiceRepository>(
  (Ref ref) => VoiceRepository(ref.watch(apiClientProvider)),
);
final specialtyRepositoryProvider = Provider<SpecialtyRepository>(
  (Ref ref) => SpecialtyRepository(ref.watch(apiClientProvider)),
);

final authRepositoryProvider = Provider<AuthRepository>(
  (Ref ref) => AuthRepository(
    ref.watch(apiClientProvider),
    ref.watch(sharedPreferencesProvider),
  ),
);

class CurrentUserNotifier extends StateNotifier<UserAccount?> {
  CurrentUserNotifier(this._authRepo) : super(_authRepo.currentUser);

  final AuthRepository _authRepo;

  void setUser(UserAccount? user) {
    state = user;
  }

  Future<void> logout() async {
    await _authRepo.logout();
    state = null;
  }
}

final currentUserProvider =
    StateNotifierProvider<CurrentUserNotifier, UserAccount?>((Ref ref) {
  return CurrentUserNotifier(ref.watch(authRepositoryProvider));
});

/// The specialty catalogue. Never fails: the repository falls back to the
/// bundled mirror of the backend's seed rows.
final specialtyCatalogProvider =
    FutureProvider<List<SpecialtyOption>>((Ref ref) {
  return ref.watch(specialtyRepositoryProvider).list();
});

/// Backend reachability, probed from the Home menu sheet.
final healthProvider = FutureProvider<bool>((Ref ref) async {
  final client = ref.watch(apiClientProvider);
  try {
    final res = await client.get<dynamic>('/api/v1/health');
    return res.meta.requestId.isNotEmpty;
  } catch (_) {
    return false;
  }
});
