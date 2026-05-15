// Firebase push notifications wiring.
//
// Marco must run `flutterfire configure` from `mobile/` and drop in the
// generated `google-services.json` (android/app/) and
// `GoogleService-Info.plist` (ios/Runner/) before this works on a device.
// Once those files exist [initialize] does the rest.
//
// On a non-mobile platform (web / desktop) [initialize] is a no-op so the
// app still boots from a dev machine.

import 'dart:io' show Platform;

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

import '../repositories/devices_repository.dart';

typedef MessageOpenedHandler = void Function(RemoteMessage message);

class PushService {
  PushService._();
  static final PushService instance = PushService._();

  final FlutterLocalNotificationsPlugin _local =
      FlutterLocalNotificationsPlugin();
  bool _initialized = false;
  String? _token;
  MessageOpenedHandler? _onMessageOpened;

  String? get token => _token;

  /// Boot Firebase + flutter_local_notifications. Safe to call multiple
  /// times. On a desktop / web / test platform it short-circuits.
  Future<void> initialize() async {
    if (_initialized) return;
    _initialized = true;
    if (!kIsWeb && !(Platform.isIOS || Platform.isAndroid)) {
      return;
    }
    try {
      await Firebase.initializeApp();
    } catch (e) {
      // Most likely cause: flutterfire configure hasn't been run. Don't
      // crash the app — push just won't work until configured.
      debugPrint('Firebase init skipped: $e');
      return;
    }

    await _local.initialize(
      const InitializationSettings(
        android: AndroidInitializationSettings('@mipmap/ic_launcher'),
        iOS: DarwinInitializationSettings(),
      ),
      onDidReceiveNotificationResponse: (resp) {
        // tapping a foreground-rendered notification — TODO: deep link.
      },
    );

    FirebaseMessaging.onMessage.listen(_showForegroundNotification);
    FirebaseMessaging.onMessageOpenedApp.listen((m) => _onMessageOpened?.call(m));
  }

  /// Called once the user is authenticated: request permission, get the FCM
  /// token, and upsert it on the backend so push can reach this device.
  Future<void> registerWithBackend(
    DevicesRepository devices, {
    String appVersion = '',
  }) async {
    if (!_initialized) await initialize();
    try {
      final messaging = FirebaseMessaging.instance;
      await messaging.requestPermission();
      _token = await messaging.getToken();
      if (_token != null) {
        await devices.register(_token!, appVersion: appVersion);
      }
      messaging.onTokenRefresh.listen((t) async {
        _token = t;
        try {
          await devices.register(t, appVersion: appVersion);
        } catch (e) {
          debugPrint('device re-register failed: $e');
        }
      });
    } catch (e) {
      debugPrint('push registration failed: $e');
    }
  }

  void setOnMessageOpened(MessageOpenedHandler? handler) {
    _onMessageOpened = handler;
  }

  Future<void> _showForegroundNotification(RemoteMessage m) async {
    final n = m.notification;
    if (n == null) return;
    await _local.show(
      n.hashCode,
      n.title,
      n.body,
      const NotificationDetails(
        android: AndroidNotificationDetails(
          'default',
          'General',
          importance: Importance.high,
        ),
        iOS: DarwinNotificationDetails(),
      ),
      payload: m.data['route'] as String?,
    );
  }
}
