# Luma Support Mobile

Flutter app for Luma Tech engineers and clients (one codebase, role-adaptive UI).

## State of the world

The Dart source compiles only after Phase 1.1 of the implementation plan
(generate platform folders, run `flutter pub get`). The app currently has:

- `dio`-based `ApiClient` with an `AuthInterceptor` that refreshes the
  JWT on 401 and replays the original request.
- Typed models (`User`, `Ticket`, `TicketNote`, `AppNotification`,
  `Article`) under `lib/src/models/`.
- Repositories under `lib/src/repositories/` for tickets, notifications,
  knowledge, devices (push tokens), and `/auth/users/me/`.
- All API paths centralised in `lib/src/services/api_paths.dart` —
  matches the DRF router layout `(/api/v1/<app>/<resource>/)`.
- `PushService` boots Firebase, registers the FCM token with the backend
  (`POST /api/v1/notifications/devices/`), and renders foreground pushes
  via `flutter_local_notifications`.
- The three existing ticket screens have been migrated off
  `Map<String,dynamic>` and now use the typed `Ticket` model.

Still TODO before public release (tracked in
`/root/.claude/plans/ok-please-can-yiu-gleaming-cupcake.md`): generate
`ios/`+`android/` folders, `go_router`, role-aware shell, new screens
(notifications inbox, KB, dashboards, client detail, profile), icons,
splash, CI, store metadata.

## Getting started

```bash
cd mobile
flutter create --platforms=ios,android --org com.lumatechsolutions \
  --project-name luma_support_mobile .   # one-off — generates ios/ + android/
flutter pub get
flutter run --dart-define=API_BASE=http://10.0.2.2:8006/api/v1   # Android emulator
```

For a real device, point `API_BASE` at your dev machine's LAN IP, e.g.
`--dart-define=API_BASE=http://192.168.1.10:8006/api/v1`.

## Push notifications

`PushService` is active. Before push will actually reach a device:

1. `dart pub global activate flutterfire_cli`.
2. `flutterfire configure` from this directory.
3. Drop the generated `google-services.json` into `android/app/` and
   `GoogleService-Info.plist` into `ios/Runner/`.
4. Upload the APNs `.p8` key in the Firebase console (Cloud Messaging →
   iOS app config).
5. On the backend, set `FCM_ENABLED=True` and `FIREBASE_CREDENTIALS_JSON`
   to the path of the Firebase Admin service-account JSON.

Once those are in place, every `Notification` row created by the backend
triggers `notifications.tasks.send_push` via the `post_save` signal, and
the device receives a push that deep-links to `/tickets/<id>`.

## Screens

- `LoginScreen` — JWT login, stored in `flutter_secure_storage`.
- `TicketListScreen` — sorted by SLA urgency, pull-to-refresh.
- `TicketDetailScreen` — update status, log time, add note.
- `TicketCreateScreen` — submit ticket with optional camera photo.

New screens (engineer dashboard, client dashboard, notifications inbox,
KB list/detail, client detail, profile) ship in Phase 2 — they all
consume the repositories already present.
