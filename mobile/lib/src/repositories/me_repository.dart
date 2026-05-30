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

  /// Begin TOTP enrolment — returns the new secret + otpauth URI to feed
  /// an authenticator app. The factor is not active until [confirmTotp].
  Future<TotpSetup> setupTotp() async {
    try {
      final res = await _api.dio.post<dynamic>(ApiPaths.totpSetup);
      final data = res.data as Map<String, dynamic>;
      return TotpSetup(
        secret: data['secret'] as String? ?? '',
        otpauthUri: data['otpauth_uri'] as String? ?? '',
      );
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// Finish TOTP enrolment by proving a current code. On success the
  /// factor is enabled and fresh recovery codes are returned (shown once).
  Future<List<String>> confirmTotp(String code) async {
    try {
      final res = await _api.dio.post<dynamic>(
        ApiPaths.totpConfirm,
        data: {'code': code},
      );
      final data = res.data as Map<String, dynamic>;
      return ((data['recovery_codes'] as List?) ?? const [])
          .map((e) => e.toString())
          .toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}

class TotpSetup {
  const TotpSetup({required this.secret, required this.otpauthUri});
  final String secret;
  final String otpauthUri;
}
