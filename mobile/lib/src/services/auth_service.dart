import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

import 'api_paths.dart';
import 'config.dart';

/// Outcome of a single login attempt — covers the 2FA-aware backend.
enum LoginResult {
  success,
  badCredentials,
  totpRequired,
  invalidTotp,
  networkError,
}

/// Holds the JWT access + refresh tokens and exposes the operations the rest
/// of the app cares about: login, refresh, logout.
///
/// The access token expires after ~60min on the backend (see
/// JWT_ACCESS_LIFETIME_MINUTES); [refresh] is invoked by the dio interceptor
/// in [AuthInterceptor] whenever a 401 comes back.
class AuthService extends ChangeNotifier {
  AuthService() {
    _restore();
  }

  static const _storage = FlutterSecureStorage();

  String? _accessToken;
  String? _refreshToken;
  bool _loading = true;

  String? get accessToken => _accessToken;
  String? get refreshToken => _refreshToken;
  bool get isAuthenticated => _accessToken != null;
  bool get loading => _loading;

  Future<void> _restore() async {
    _accessToken = await _storage.read(key: 'access');
    _refreshToken = await _storage.read(key: 'refresh');
    _loading = false;
    notifyListeners();
  }

  /// Attempt a login, optionally with a TOTP code. The backend may return
  /// 401 with {"detail":"totp_required"|"invalid_totp"} to signal the
  /// second-factor step — callers should re-prompt and call this again
  /// with [totpCode] populated.
  Future<LoginResult> login(
    String email,
    String password, {
    String? totpCode,
  }) async {
    final body = <String, String>{
      'email': email,
      'password': password,
    };
    if (totpCode != null && totpCode.isNotEmpty) {
      body['totp_code'] = totpCode;
    }
    http.Response res;
    try {
      res = await http.post(
        Uri.parse('$kApiBase${ApiPaths.login}'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(body),
      );
    } catch (_) {
      return LoginResult.networkError;
    }
    if (res.statusCode == 200) {
      final data = jsonDecode(res.body) as Map<String, dynamic>;
      await _storeTokens(
        access: data['access'] as String?,
        refresh: data['refresh'] as String?,
      );
      return _accessToken != null
          ? LoginResult.success
          : LoginResult.badCredentials;
    }
    if (res.statusCode == 401) {
      try {
        final data = jsonDecode(res.body);
        if (data is Map && data['detail'] == 'totp_required') {
          return LoginResult.totpRequired;
        }
        if (data is Map && data['detail'] == 'invalid_totp') {
          return LoginResult.invalidTotp;
        }
      } catch (_) {}
      return LoginResult.badCredentials;
    }
    return LoginResult.networkError;
  }

  /// Exchange the stored refresh token for a new access token. Returns false
  /// (and logs the caller out) on any failure.
  Future<bool> refresh() async {
    final refresh = _refreshToken;
    if (refresh == null) return false;
    final res = await http.post(
      Uri.parse('$kApiBase${ApiPaths.refresh}'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'refresh': refresh}),
    );
    if (res.statusCode != 200) {
      await logout();
      return false;
    }
    final data = jsonDecode(res.body) as Map<String, dynamic>;
    await _storeTokens(access: data['access'] as String?);
    return _accessToken != null;
  }

  Future<void> logout() async {
    await _storage.deleteAll();
    _accessToken = null;
    _refreshToken = null;
    notifyListeners();
  }

  Future<void> _storeTokens({String? access, String? refresh}) async {
    if (access != null) {
      _accessToken = access;
      await _storage.write(key: 'access', value: access);
    }
    if (refresh != null) {
      _refreshToken = refresh;
      await _storage.write(key: 'refresh', value: refresh);
    }
    notifyListeners();
  }
}
