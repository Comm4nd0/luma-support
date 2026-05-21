import 'package:flutter/material.dart';
import 'package:local_auth/local_auth.dart';

import 'settings_service.dart';

/// Tracks whether the app is currently "locked" behind a biometric
/// prompt and listens to lifecycle events so the lock re-asserts on
/// every foreground return.
///
/// Wired together by [AppLockGate]: the gate listens to this service
/// and overlays a full-screen "tap to unlock" UI when [locked] is
/// true. The service never decides whether locking is required —
/// that's [SettingsService.biometricRequired]; this just tracks state.
class AppLockService extends ChangeNotifier with WidgetsBindingObserver {
  AppLockService(this._settings) {
    WidgetsBinding.instance.addObserver(this);
    _settings.addListener(_onSettingsChanged);
    _syncFromSettings();
  }

  final SettingsService _settings;
  final LocalAuthentication _auth = LocalAuthentication();

  bool _locked = false;
  bool _backgrounded = false;
  bool _attempting = false;

  bool get locked => _locked;
  bool get attempting => _attempting;
  bool get biometricRequired => _settings.biometricRequired;

  void _onSettingsChanged() {
    // Turning the toggle off should unlock immediately so the user
    // isn't stranded behind a now-stale lock screen.
    if (!_settings.biometricRequired && _locked) {
      _locked = false;
      notifyListeners();
    }
  }

  void _syncFromSettings() {
    // First boot: if a returning user has biometric_required on, start
    // locked. (Settings.load() runs before the first frame.)
    if (_settings.biometricRequired) {
      _locked = true;
      notifyListeners();
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.hidden) {
      _backgrounded = true;
    } else if (state == AppLifecycleState.resumed) {
      if (_backgrounded && _settings.biometricRequired) {
        _locked = true;
        notifyListeners();
      }
      _backgrounded = false;
    }
  }

  /// Prompt the user for biometric auth. Sets [locked] = false on
  /// success. On a failed / cancelled prompt the lock stays in place.
  Future<bool> unlock() async {
    if (_attempting) return false;
    _attempting = true;
    notifyListeners();
    try {
      final ok = await _auth.authenticate(
        localizedReason: 'Unlock Luma Tech Solutions',
        options: const AuthenticationOptions(
          biometricOnly: false,
          stickyAuth: true,
        ),
      );
      if (ok) {
        _locked = false;
      }
      return ok;
    } catch (_) {
      return false;
    } finally {
      _attempting = false;
      notifyListeners();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _settings.removeListener(_onSettingsChanged);
    super.dispose();
  }
}
