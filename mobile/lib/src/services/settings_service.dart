import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// User-tweakable app preferences.
///
/// Stored in shared_preferences so they survive restarts. The server
/// also tracks per-user quiet hours (see User.quiet_hours_* on the
/// backend); this service hydrates locally first for instant UX and
/// pushes server-side via [pushToServer] when the user has internet.
class SettingsService extends ChangeNotifier {
  SettingsService();

  static const _kThemeMode = 'settings.themeMode';
  static const _kBiometricRequired = 'settings.biometricRequired';
  static const _kQuietStart = 'settings.quietStart';
  static const _kQuietEnd = 'settings.quietEnd';
  static const _kQuietCriticalOverride = 'settings.quietCriticalOverride';

  ThemeMode _themeMode = ThemeMode.system;
  bool _biometricRequired = false;
  int? _quietStart;
  int? _quietEnd;
  bool _quietCriticalOverride = true;
  bool _loaded = false;

  ThemeMode get themeMode => _themeMode;
  bool get biometricRequired => _biometricRequired;
  int? get quietHoursStart => _quietStart;
  int? get quietHoursEnd => _quietEnd;
  bool get quietHoursCriticalOverride => _quietCriticalOverride;
  bool get loaded => _loaded;
  bool get hasQuietHours => _quietStart != null && _quietEnd != null;

  Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();
    final mode = prefs.getString(_kThemeMode);
    switch (mode) {
      case 'dark':
        _themeMode = ThemeMode.dark;
        break;
      case 'light':
        _themeMode = ThemeMode.light;
        break;
      default:
        _themeMode = ThemeMode.system;
    }
    _biometricRequired = prefs.getBool(_kBiometricRequired) ?? false;
    _quietStart = prefs.getInt(_kQuietStart);
    _quietEnd = prefs.getInt(_kQuietEnd);
    _quietCriticalOverride =
        prefs.getBool(_kQuietCriticalOverride) ?? true;
    _loaded = true;
    notifyListeners();
  }

  Future<void> setThemeMode(ThemeMode mode) async {
    _themeMode = mode;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kThemeMode, _modeToWire(mode));
    notifyListeners();
  }

  Future<void> setBiometricRequired(bool value) async {
    _biometricRequired = value;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_kBiometricRequired, value);
    notifyListeners();
  }

  Future<void> setQuietHours({
    required int? start,
    required int? end,
    required bool criticalOverride,
  }) async {
    _quietStart = start;
    _quietEnd = end;
    _quietCriticalOverride = criticalOverride;
    final prefs = await SharedPreferences.getInstance();
    if (start == null) {
      await prefs.remove(_kQuietStart);
    } else {
      await prefs.setInt(_kQuietStart, start);
    }
    if (end == null) {
      await prefs.remove(_kQuietEnd);
    } else {
      await prefs.setInt(_kQuietEnd, end);
    }
    await prefs.setBool(_kQuietCriticalOverride, criticalOverride);
    notifyListeners();
  }

  /// Hydrate quiet-hours fields from the /me payload so a user who
  /// already configured them on web sees the same window on mobile.
  Future<void> hydrateFromServer(Map<String, dynamic> meJson) async {
    final start = meJson['quiet_hours_start'] as int?;
    final end = meJson['quiet_hours_end'] as int?;
    final critical =
        meJson['quiet_hours_critical_override'] as bool? ?? true;
    await setQuietHours(start: start, end: end, criticalOverride: critical);
  }

  static String _modeToWire(ThemeMode mode) {
    switch (mode) {
      case ThemeMode.dark:
        return 'dark';
      case ThemeMode.light:
        return 'light';
      case ThemeMode.system:
        return 'system';
    }
  }
}
