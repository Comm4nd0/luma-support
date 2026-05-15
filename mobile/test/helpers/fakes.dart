import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import 'package:luma_support_mobile/src/services/api_client.dart';
import 'package:luma_support_mobile/src/services/auth_service.dart';

/// In-memory AuthService for widget tests — never touches
/// flutter_secure_storage so it works without a platform channel.
class FakeAuthService extends ChangeNotifier implements AuthService {
  FakeAuthService({String? access, String? refresh})
      : _access = access,
        _refresh = refresh;

  String? _access;
  String? _refresh;

  @override
  String? get accessToken => _access;

  @override
  String? get refreshToken => _refresh;

  @override
  bool get isAuthenticated => _access != null;

  @override
  bool get loading => false;

  @override
  Future<bool> login(String email, String password) async {
    _access = 'fake-access';
    _refresh = 'fake-refresh';
    notifyListeners();
    return true;
  }

  @override
  Future<bool> refresh() async => true;

  @override
  Future<void> logout() async {
    _access = null;
    _refresh = null;
    notifyListeners();
  }
}

/// Convenience constructor for an ApiClient backed by a hand-rolled Dio.
ApiClient fakeApiClient(Dio dio) => ApiClient.withDio(dio);
