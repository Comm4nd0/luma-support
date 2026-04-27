# Luma Support Mobile

Flutter app for Luma Tech engineers and clients.

## Getting started

```bash
flutter pub get
flutter run --dart-define=API_BASE=http://10.0.2.2:8006/api/v1   # Android emulator -> host
```

For a real device, point `API_BASE` at your dev machine's LAN IP, e.g.
`--dart-define=API_BASE=http://192.168.1.10:8006/api/v1`.

## Push notifications

The `PushService` is scaffolded but inactive. To enable:

1. `dart pub global activate flutterfire_cli`
2. `flutterfire configure` from this directory.
3. Drop the generated config files into `android/app/` and `ios/Runner/`.
4. Uncomment the `Firebase.initializeApp` block in `lib/src/services/push_service.dart`.

## Screens

- `LoginScreen` — JWT login, stored in `flutter_secure_storage`.
- `TicketListScreen` — sorted by SLA urgency.
- `TicketDetailScreen` — update status, log time, add note.
- `TicketCreateScreen` — submit ticket with optional camera photo.
