import '../constants/api_paths.dart';
import '../models/json_utils.dart';
import '../models/specialty.dart';
import '../networking/api_client.dart';

/// `GET /api/v1/specialties` — the routing catalogue behind §9.13.
///
/// The backend owns this list (it is what `POST /brief` validates a specialty
/// against), so the picker reads it rather than a second hardcoded copy. If the
/// call fails the repository falls back to [SpecialtyOption.mirroringBackend],
/// which mirrors the backend's seed rows — the app is therefore usable offline
/// and can never offer a specialty the backend will reject.
class SpecialtyRepository {
  SpecialtyRepository(this._client);

  final ApiClient _client;

  Future<List<SpecialtyOption>> list() async {
    try {
      final res = await _client.get<dynamic>(
        ApiPaths.specialties,
        parse: (dynamic d) => asMapList(d)
            .map(SpecialtyOption.fromJson)
            .toList(growable: false),
      );
      final fetched = res.data;
      if (fetched.isNotEmpty) return fetched;
    } catch (_) {
      // Fall through to the bundled mirror.
    }
    return SpecialtyOption.mirroringBackend();
  }
}
