import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import 'package:luma_support_mobile/src/models/user.dart';
import 'package:luma_support_mobile/src/services/api_client.dart';
import 'package:luma_support_mobile/src/services/auth_service.dart';
import 'package:luma_support_mobile/src/services/current_user.dart';

/// In-memory AuthService for widget tests — never touches
/// flutter_secure_storage so it works without a platform channel.
class FakeAuthService extends ChangeNotifier implements AuthService {
  FakeAuthService({
    String? access,
    String? refresh,
    this.totpRequired = false,
    this.expectedTotpCode,
  })  : _access = access,
        _refresh = refresh;

  String? _access;
  String? _refresh;

  /// Toggle on to make [login] return [LoginResult.totpRequired] until
  /// [expectedTotpCode] is supplied. Lets the widget test exercise the
  /// 2FA flow without a real backend.
  bool totpRequired;
  String? expectedTotpCode;

  @override
  String? get accessToken => _access;

  @override
  String? get refreshToken => _refresh;

  @override
  bool get isAuthenticated => _access != null;

  @override
  bool get loading => false;

  @override
  Future<LoginResult> login(
    String email,
    String password, {
    String? totpCode,
    String? recoveryCode,
  }) async {
    if (totpRequired) {
      if (totpCode == null || totpCode.isEmpty) {
        return LoginResult.totpRequired;
      }
      if (expectedTotpCode != null && totpCode != expectedTotpCode) {
        return LoginResult.invalidTotp;
      }
    }
    _access = 'fake-access';
    _refresh = 'fake-refresh';
    notifyListeners();
    return LoginResult.success;
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

/// Role-stub for [CurrentUser] — returns a fixed user without a `/me`
/// fetch. `implements` (not extends) so no production field state leaks
/// into the test.
class FakeCurrentUser extends ChangeNotifier implements CurrentUser {
  FakeCurrentUser([this._user]);
  final AppUser? _user;

  @override
  AppUser? get user => _user;
  @override
  bool get loading => false;
  @override
  bool get isStaff => _user?.canViewAll ?? false;
  @override
  bool get isClient => _user?.isClient ?? false;
  @override
  bool get isAdmin => _user?.isAdmin ?? false;
  @override
  Future<void> fetch(ApiClient api) async {}
  @override
  void clear() {}
}

/// A staff engineer AppUser for tests that just need "someone staff".
AppUser fakeEngineerUser() => AppUser(
      id: 1,
      email: 'eng@example.com',
      firstName: 'Eng',
      lastName: '',
      role: UserRole.engineer,
      phone: '',
      clientId: null,
      isStaff: true,
      isActive: true,
      quietHoursStart: null,
      quietHoursEnd: null,
      quietHoursCriticalOverride: true,
      totpEnabled: false,
    );
