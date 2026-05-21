import 'package:dio/dio.dart';

import '../models/user.dart';
import '../services/api_client.dart';
import '../services/api_paths.dart';

class MeRepository {
  MeRepository(this._api);

  final ApiClient _api;

  Future<AppUser> fetch() async {
    try {
      final res = await _api.dio.get<dynamic>(ApiPaths.me);
      return AppUser.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// Regenerate the user's 2FA recovery codes. Plaintext codes come back
  /// once — surface them in the UI immediately, never persist them on the
  /// device.
  Future<List<String>> regenerateRecoveryCodes() async {
    try {
      final res = await _api.dio.post<dynamic>(ApiPaths.recoveryCodes);
      final data = res.data as Map<String, dynamic>;
      return ((data['codes'] as List?) ?? const [])
          .map((e) => e.toString())
          .toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}
