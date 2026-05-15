import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:mocktail/mocktail.dart';
import 'package:provider/provider.dart';

import 'package:luma_support_mobile/src/screens/ticket_list_screen.dart';
import 'package:luma_support_mobile/src/services/api_client.dart';
import 'package:luma_support_mobile/src/services/auth_service.dart';

import '../helpers/fakes.dart';
import '../helpers/mock_dio.dart';

void main() {
  setUpAll(registerMockFallbacks);

  Widget wrap({required ApiClient api, required AuthService auth}) {
    final router = GoRouter(
      initialLocation: '/tickets',
      routes: [
        GoRoute(path: '/tickets', builder: (_, __) => const TicketListScreen()),
        GoRoute(path: '/tickets/new', builder: (_, __) => const Scaffold()),
        GoRoute(
          path: '/tickets/:id',
          builder: (_, __) => const Scaffold(body: Text('detail')),
        ),
      ],
    );
    return MultiProvider(
      providers: [
        ChangeNotifierProvider<AuthService>.value(value: auth),
        Provider<ApiClient>.value(value: api),
      ],
      child: MaterialApp.router(routerConfig: router),
    );
  }

  testWidgets('renders ticket rows from the API', (tester) async {
    final dio = MockDio();
    when(() => dio.get<dynamic>(
          any(),
          queryParameters: any(named: 'queryParameters'),
        )).thenAnswer((_) async => okResponse('/tickets/tickets/', {
          'results': [
            {
              'id': 1,
              'client': 1,
              'client_name': 'Acme',
              'subject': 'Wi-Fi down',
              'description': '',
              'priority': 'high',
              'status': 'in_progress',
              'is_breached': false,
              'created_at': '2026-05-15T09:00:00Z',
            },
            {
              'id': 2,
              'client': 1,
              'client_name': 'Acme',
              'subject': 'Lights flicker',
              'description': '',
              'priority': 'low',
              'status': 'new',
              'is_breached': true,
              'created_at': '2026-05-15T09:00:00Z',
            },
          ]
        }));
    await tester.pumpWidget(
      wrap(api: ApiClient.withDio(dio), auth: FakeAuthService(access: 't')),
    );
    await tester.pumpAndSettle();
    expect(find.text('Wi-Fi down'), findsOneWidget);
    expect(find.text('Lights flicker'), findsOneWidget);
    expect(find.text('BREACHED'), findsOneWidget);
  });

  testWidgets('shows empty state when no tickets', (tester) async {
    final dio = MockDio();
    when(() => dio.get<dynamic>(
          any(),
          queryParameters: any(named: 'queryParameters'),
        )).thenAnswer(
      (_) async => okResponse('/tickets/tickets/', {'results': []}),
    );
    await tester.pumpWidget(
      wrap(api: ApiClient.withDio(dio), auth: FakeAuthService(access: 't')),
    );
    await tester.pumpAndSettle();
    expect(find.text('No tickets yet.'), findsOneWidget);
  });

  testWidgets('shows error state when the API fails', (tester) async {
    final dio = MockDio();
    when(() => dio.get<dynamic>(
          any(),
          queryParameters: any(named: 'queryParameters'),
        )).thenThrow(dioError('/tickets/tickets/', statusCode: 500));
    await tester.pumpWidget(
      wrap(api: ApiClient.withDio(dio), auth: FakeAuthService(access: 't')),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('Error'), findsOneWidget);
  });
}
