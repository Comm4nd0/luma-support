import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:go_router/go_router.dart';

import 'push_service.dart';

/// Glue between [PushService] and [GoRouter]. When a push notification is
/// tapped — either from the background (`onMessageOpenedApp`) or to launch
/// the app from killed state (`getInitialMessage`) — we read the `route`
/// key out of the FCM `data` payload and navigate there.
class PushRouter {
  PushRouter._();
  static final PushRouter instance = PushRouter._();

  GoRouter? _router;

  /// Attach the app's router. Call once during app bootstrap, after the
  /// `GoRouter` has been built.
  void attach(GoRouter router) {
    _router = router;

    PushService.instance.setOnMessageOpened(_handle);

    // Cold-start case: the OS opened the app from a notification tap.
    FirebaseMessaging.instance.getInitialMessage().then((m) {
      if (m != null) _handle(m);
    }).catchError((_) {});
  }

  void _handle(RemoteMessage message) {
    final route = message.data['route'];
    if (route is String && route.isNotEmpty) {
      _router?.go(route);
    }
  }
}
