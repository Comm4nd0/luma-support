import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:luma_support_mobile/src/repositories/notifications_repository.dart';
import 'package:luma_support_mobile/src/services/api_paths.dart';

import '../helpers/mock_dio.dart';

void main() {
  setUpAll(registerMockFallbacks);

  test('list() parses results array', () async {
    final ctx = buildApi();
    when(() => ctx.dio.get<dynamic>(
          any(),
          queryParameters: any(named: 'queryParameters'),
        )).thenAnswer((_) async => okResponse(ApiPaths.notifications, {
          'results': [
            {
              'id': 1,
              'type': 'sla_warning',
              'title': 'SLA breached',
              'body': '...',
              'related_ticket': 99,
              'read': false,
              'created_at': '2026-05-15T08:00:00Z',
            }
          ]
        }));
    final items = await NotificationsRepository(ctx.api).list();
    expect(items, hasLength(1));
    expect(items.first.type, 'sla_warning');
    expect(items.first.relatedTicketId, 99);
  });

  test('list(unreadOnly: true) sends read=false query', () async {
    final ctx = buildApi();
    Map<String, dynamic>? captured;
    when(() => ctx.dio.get<dynamic>(
          any(),
          queryParameters: any(named: 'queryParameters'),
        )).thenAnswer((invocation) async {
      captured = invocation.namedArguments[const Symbol('queryParameters')]
          as Map<String, dynamic>;
      return okResponse(ApiPaths.notifications, {'results': []});
    });
    await NotificationsRepository(ctx.api).list(unreadOnly: true);
    expect(captured?['read'], 'false');
  });

  test('unreadCount() returns int from {count}', () async {
    final ctx = buildApi();
    when(() => ctx.dio.get<dynamic>(any())).thenAnswer(
      (_) async => okResponse(ApiPaths.notificationsUnreadCount, {'count': 3}),
    );
    expect(await NotificationsRepository(ctx.api).unreadCount(), 3);
  });

  test('markRead posts to the mark-read action', () async {
    final ctx = buildApi();
    String? path;
    when(() => ctx.dio.post<dynamic>(any())).thenAnswer((invocation) async {
      path = invocation.positionalArguments.first as String;
      return okResponse(path!, {});
    });
    await NotificationsRepository(ctx.api).markRead(42);
    expect(path, ApiPaths.notificationMarkRead(42));
  });
}
