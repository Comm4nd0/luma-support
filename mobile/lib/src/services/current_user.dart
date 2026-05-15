import 'package:flutter/foundation.dart';

import '../models/user.dart';
import '../repositories/me_repository.dart';
import 'api_client.dart';

/// Holds the logged-in [AppUser]. The role drives navigation: client users
/// see [ClientShell], staff see [EngineerShell]. Cleared on logout.
class CurrentUser extends ChangeNotifier {
  AppUser? _user;
  bool _loading = false;

  AppUser? get user => _user;
  bool get loading => _loading;
  bool get isStaff => _user?.canViewAll ?? false;
  bool get isClient => _user?.isClient ?? false;
  bool get isAdmin => _user?.isAdmin ?? false;

  Future<void> fetch(ApiClient api) async {
    _loading = true;
    notifyListeners();
    try {
      _user = await MeRepository(api).fetch();
    } finally {
      _loading = false;
      notifyListeners();
    }
  }

  void clear() {
    _user = null;
    notifyListeners();
  }
}
