// Firebase push notifications wiring.
//
// This is intentionally a thin scaffold — the developer must run
// `flutterfire configure` and drop in google-services.json /
// GoogleService-Info.plist before push will actually work on a device.
//
// Until then `initialize()` is a no-op so the app still boots.

import 'package:flutter/foundation.dart';

class PushService {
  PushService._();
  static final PushService instance = PushService._();

  Future<void> initialize() async {
    // TODO: enable once Firebase is configured for the project:
    //
    //   await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);
    //   final messaging = FirebaseMessaging.instance;
    //   await messaging.requestPermission();
    //   final token = await messaging.getToken();
    //   FirebaseMessaging.onMessage.listen((m) { /* show local notif */ });
    if (kDebugMode) {
      // Replace with real `debugPrint` to a logger of your choice.
    }
  }
}
