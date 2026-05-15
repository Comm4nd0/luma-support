import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:provider/provider.dart';

import 'package:luma_support_mobile/src/models/user.dart';
import 'package:luma_support_mobile/src/screens/ticket_detail_screen.dart';
import 'package:luma_support_mobile/src/services/api_client.dart';
import 'package:luma_support_mobile/src/services/auth_service.dart';
import 'package:luma_support_mobile/src/services/current_user.dart';

import '../helpers/fakes.dart';
import '../helpers/mock_dio.dart';

/// Thin replacement for [CurrentUser] that returns a known role without
/// needing a real `/me` fetch. We use `implements` (not extends) so we
/// don't carry the production field state into the test.
class _StubCurrentUser extends ChangeNotifier implements CurrentUser {
  _StubCurrentUser(this._user);
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
  Future<void> fetch(ApiClient api) async {}
  @override
  void clear() {}
}

AppUser _engineer() => AppUser(
      id: 1,
      email: 'eng@example.com',
      firstName: 'Eng',
      lastName: '',
      role: UserRole.engineer,
      phone: '',
      clientId: null,
      isStaff: true,
      isActive: true,
    );

AppUser _client() => AppUser(
      id: 2,
      email: 'customer@example.com',
      firstName: 'Cust',
      lastName: '',
      role: UserRole.client,
      phone: '',
      clientId: 5,
      isStaff: false,
      isActive: true,
    );

void main() {
  setUpAll(registerMockFallbacks);

  Widget wrap({required AppUser user, required ApiClient api}) {
    return MaterialApp(
      home: MultiProvider(
        providers: [
          ChangeNotifierProvider<AuthService>.value(
              value: FakeAuthService(access: 't')),
          Provider<ApiClient>.value(value: api),
          ChangeNotifierProvider<CurrentUser>.value(
              value: _StubCurrentUser(user)),
        ],
        child: const TicketDetailScreen(ticketId: 99),
      ),
    );
  }

  ApiClient apiReturning(Map<String, dynamic> ticket) {
    final dio = MockDio();
    when(() => dio.get<dynamic>(any())).thenAnswer(
      (_) async => okResponse('/tickets/tickets/99/', ticket),
    );
    return ApiClient.withDio(dio);
  }

  final ticketJson = <String, dynamic>{
    'id': 99,
    'client': 5,
    'client_name': 'Acme',
    'subject': 'Wi-Fi flaky',
    'description': 'On and off',
    'priority': 'high',
    'status': 'in_progress',
    'is_breached': false,
    'created_at': '2026-05-15T09:00:00Z',
  };

  testWidgets('engineer sees status buttons + Log time + Add note',
      (tester) async {
    await tester
        .pumpWidget(wrap(user: _engineer(), api: apiReturning(ticketJson)));
    await tester.pumpAndSettle();
    expect(find.text('Log time'), findsOneWidget);
    expect(find.text('Add note'), findsOneWidget);
    expect(find.text('resolved'), findsOneWidget); // status button
  });

  testWidgets('client only sees Add note', (tester) async {
    await tester
        .pumpWidget(wrap(user: _client(), api: apiReturning(ticketJson)));
    await tester.pumpAndSettle();
    expect(find.text('Add note'), findsOneWidget);
    expect(find.text('Log time'), findsNothing);
    expect(find.text('resolved'), findsNothing);
  });
}
