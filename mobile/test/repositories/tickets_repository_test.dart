import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:luma_support_mobile/src/models/ticket.dart';
import 'package:luma_support_mobile/src/repositories/tickets_repository.dart';
import 'package:luma_support_mobile/src/services/api_client.dart';
import 'package:luma_support_mobile/src/services/api_paths.dart';

import '../helpers/mock_dio.dart';

void main() {
  setUpAll(registerMockFallbacks);

  group('TicketsRepository.list', () {
    test('parses paginated DRF response into Tickets', () async {
      final ctx = buildApi();
      when(() => ctx.dio.get<dynamic>(
            any(),
            queryParameters: any(named: 'queryParameters'),
          )).thenAnswer((_) async => okResponse(
            ApiPaths.tickets,
            {
              'count': 1,
              'results': [
                {
                  'id': 7,
                  'client': 1,
                  'client_name': 'Acme',
                  'subject': 'Wi-Fi down',
                  'description': 'It is dead.',
                  'priority': 'high',
                  'status': 'in_progress',
                  'sla_deadline': '2026-05-15T13:00:00Z',
                  'is_breached': false,
                  'assigned_to_email': 'eng@example.com',
                  'created_at': '2026-05-15T09:00:00Z',
                },
              ],
            },
          ));
      final tickets = await TicketsRepository(ctx.api).list();
      expect(tickets, hasLength(1));
      expect(tickets.first.id, 7);
      expect(tickets.first.subject, 'Wi-Fi down');
      expect(tickets.first.priority, TicketPriority.high);
      expect(tickets.first.status, TicketStatus.inProgress);
    });

    test('passes status and priority as query params', () async {
      final ctx = buildApi();
      Map<String, dynamic>? captured;
      when(() => ctx.dio.get<dynamic>(
            any(),
            queryParameters: any(named: 'queryParameters'),
          )).thenAnswer((invocation) async {
        captured = invocation.namedArguments[const Symbol('queryParameters')]
            as Map<String, dynamic>;
        return okResponse(ApiPaths.tickets, {'results': []});
      });
      await TicketsRepository(ctx.api).list(status: 'new', priority: 'low');
      expect(captured?['status'], 'new');
      expect(captured?['priority'], 'low');
    });

    test('wraps DioException as ApiException', () async {
      final ctx = buildApi();
      when(() => ctx.dio.get<dynamic>(
            any(),
            queryParameters: any(named: 'queryParameters'),
          )).thenThrow(dioError(ApiPaths.tickets, statusCode: 502));
      await expectLater(
        TicketsRepository(ctx.api).list(),
        throwsA(isA<ApiException>().having((e) => e.statusCode, 'status', 502)),
      );
    });
  });

  group('TicketsRepository.dashboardStats', () {
    test('parses KPI bundle including the SLA digest', () async {
      final ctx = buildApi();
      when(() => ctx.dio.get<dynamic>(any())).thenAnswer(
        (_) async => okResponse(ApiPaths.dashboardStats, {
          'unbilled_hours': 3.5,
          'mtd_invoiced': '1200.00',
          'mtd_paid': '800.00',
          'overdue_invoices': 2,
          'maintenance_due_7d': 1,
          'currency': 'GBP',
          'social_accounts': [],
          'social_inbox_unread': 0,
          'sla_digest': {
            'within_hours': 8,
            'breached': 1,
            'approaching': 3,
            'total': 4,
          },
        }),
      );
      final stats = await TicketsRepository(ctx.api).dashboardStats();
      expect(stats.unbilledHours, 3.5);
      expect(stats.overdueInvoices, 2);
      expect(stats.slaDigestWithinHours, 8);
      expect(stats.slaDigestBreached, 1);
      expect(stats.slaDigestApproaching, 3);
    });

    test('defaults the SLA digest when the key is absent', () async {
      final ctx = buildApi();
      when(() => ctx.dio.get<dynamic>(any())).thenAnswer(
        (_) async => okResponse(ApiPaths.dashboardStats, {
          'unbilled_hours': 0,
          'mtd_invoiced': '0',
          'mtd_paid': '0',
          'overdue_invoices': 0,
          'maintenance_due_7d': 0,
          'currency': 'GBP',
          'social_accounts': [],
          'social_inbox_unread': 0,
        }),
      );
      final stats = await TicketsRepository(ctx.api).dashboardStats();
      expect(stats.slaDigestWithinHours, 8);
      expect(stats.slaDigestBreached, 0);
      expect(stats.slaDigestApproaching, 0);
    });
  });

  group('TicketsRepository.get', () {
    test('returns a single ticket', () async {
      final ctx = buildApi();
      when(() => ctx.dio.get<dynamic>(any())).thenAnswer(
        (_) async => okResponse(ApiPaths.ticket(3), {
          'id': 3,
          'client': 1,
          'client_name': 'Acme',
          'subject': 'x',
          'description': '',
          'priority': 'low',
          'status': 'new',
          'is_breached': false,
          'created_at': '2026-05-15T09:00:00Z',
        }),
      );
      final t = await TicketsRepository(ctx.api).get(3);
      expect(t.id, 3);
      expect(t.priority, TicketPriority.low);
      expect(t.status, TicketStatus.newTicket);
    });
  });

  group('TicketsRepository.setStatus', () {
    test('POSTs the wire-formatted status', () async {
      final ctx = buildApi();
      String? capturedPath;
      Map<String, dynamic>? capturedBody;
      when(() => ctx.dio.post<dynamic>(
            any(),
            data: any(named: 'data'),
          )).thenAnswer((invocation) async {
        capturedPath = invocation.positionalArguments.first as String;
        capturedBody = invocation.namedArguments[const Symbol('data')]
            as Map<String, dynamic>;
        return okResponse(capturedPath!, {});
      });
      await TicketsRepository(ctx.api).setStatus(9, TicketStatus.inProgress);
      expect(capturedPath, ApiPaths.ticketStatus(9));
      expect(capturedBody?['status'], 'in_progress');
    });
  });

  group('TicketsRepository.addNote', () {
    test('POSTs body and parses TicketNote', () async {
      final ctx = buildApi();
      when(() => ctx.dio.post<dynamic>(
            any(),
            data: any(named: 'data'),
          )).thenAnswer((invocation) async {
        final body =
            invocation.namedArguments[const Symbol('data')] as Map<String, dynamic>;
        return okResponse('/notes', {
          'id': 1,
          'ticket': 9,
          'author_email': 'eng@example.com',
          'body': body['body'],
          'internal': body['internal'],
          'created_at': '2026-05-15T09:00:00Z',
        });
      });
      final note = await TicketsRepository(ctx.api)
          .addNote(9, 'Looking into it', internal: false);
      expect(note.body, 'Looking into it');
      expect(note.internal, false);
    });
  });
}
