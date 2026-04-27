import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

import 'config.dart';

class AuthService extends ChangeNotifier {
  AuthService() {
    _restore();
  }

  static const _storage = FlutterSecureStorage();

  String? _accessToken;
  String? _refreshToken;
  bool loading = true;

  String? get accessToken => _accessToken;
  bool get isAuthenticated => _accessToken != null;

  Future<void> _restore() async {
    _accessToken = await _storage.read(key: 'access');
    _refreshToken = await _storage.read(key: 'refresh');
    loading = false;
    notifyListeners();
  }

  Future<bool> login(String email, String password) async {
    final res = await http.post(
      Uri.parse('${kApiBase}/auth/jwt/create/'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'email': email, 'password': password}),
    );
    if (res.statusCode != 200) return false;
    final data = jsonDecode(res.body) as Map<String, dynamic>;
    _accessToken = data['access'] as String?;
    _refreshToken = data['refresh'] as String?;
    if (_accessToken != null) {
      await _storage.write(key: 'access', value: _accessToken);
    }
    if (_refreshToken != null) {
      await _storage.write(key: 'refresh', value: _refreshToken);
    }
    notifyListeners();
    return _accessToken != null;
  }

  Future<void> logout() async {
    await _storage.deleteAll();
    _accessToken = null;
    _refreshToken = null;
    notifyListeners();
  }
}
