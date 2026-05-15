import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:luma_support_mobile/src/models/invoice.dart';
import 'package:luma_support_mobile/src/repositories/invoices_repository.dart';
import 'package:luma_support_mobile/src/services/api_client.dart';
import 'package:luma_support_mobile/src/services/api_paths.dart';

import '../helpers/mock_dio.dart';

void main() {
  setUpAll(registerMockFallbacks);

  group('InvoicesRepository.list', () {
    test('parses paginated DRF response into Invoices with lines', () async {
      final ctx = buildApi();
      when(() => ctx.dio.get<dynamic>(
            any(),
            queryParameters: any(named: 'queryParameters'),
          )).thenAnswer((_) async => okResponse(
            ApiPaths.invoices,
            {
              'count': 1,
              'results': [
                {
                  'id': 11,
                  'client': 3,
                  'kind': 'one_off',
                  'status': 'sent',
                  'subtotal': '100.00',
                  'tax': '20.00',
                  'total': '120.00',
                  'currency': 'GBP',
                  'due_date': '2026-06-15',
                  'notes': '',
                  'xero_invoice_id': 'XR-1',
                  'xero_status': 'AUTHORISED',
                  'xero_synced_at': '2026-05-15T11:00:00Z',
                  'sent_at': null,
                  'paid_at': null,
                  'lines': [
                    {
                      'id': 1,
                      'description': 'Wi-Fi survey',
                      'quantity': '2.00',
                      'unit_amount': '50.00',
                      'line_total': '100.00',
                      'account_code': '200',
                      'tax_type': 'OUTPUT2',
                      'time_entry': null,
                    },
                  ],
                  'created_at': '2026-05-15T09:00:00Z',
                  'updated_at': '2026-05-15T09:00:00Z',
                },
              ],
            },
          ));
      final invoices = await InvoicesRepository(ctx.api).list();
      expect(invoices, hasLength(1));
      final inv = invoices.first;
      expect(inv.id, 11);
      expect(inv.status, InvoiceStatus.sent);
      expect(inv.kind, InvoiceKind.oneOff);
      expect(inv.total, 120.0);
      expect(inv.isSyncedToXero, isTrue);
      expect(inv.lines, hasLength(1));
      expect(inv.lines.first.description, 'Wi-Fi survey');
      expect(inv.lines.first.lineTotal, 100.0);
    });

    test('forwards client and status as query params', () async {
      final ctx = buildApi();
      Map<String, dynamic>? captured;
      when(() => ctx.dio.get<dynamic>(
            any(),
            queryParameters: any(named: 'queryParameters'),
          )).thenAnswer((invocation) async {
        captured = invocation.namedArguments[const Symbol('queryParameters')]
            as Map<String, dynamic>;
        return okResponse(ApiPaths.invoices, {'results': []});
      });
      await InvoicesRepository(ctx.api)
          .list(clientId: 7, status: InvoiceStatus.paid);
      expect(captured?['client'], 7);
      expect(captured?['status'], 'paid');
    });

    test('wraps DioException as ApiException', () async {
      final ctx = buildApi();
      when(() => ctx.dio.get<dynamic>(
            any(),
            queryParameters: any(named: 'queryParameters'),
          )).thenThrow(dioError(ApiPaths.invoices, statusCode: 403));
      await expectLater(
        InvoicesRepository(ctx.api).list(),
        throwsA(isA<ApiException>().having((e) => e.statusCode, 'status', 403)),
      );
    });
  });

  group('InvoicesRepository.get', () {
    test('returns a single invoice with empty xero fields when not synced',
        () async {
      final ctx = buildApi();
      when(() => ctx.dio.get<dynamic>(any())).thenAnswer(
        (_) async => okResponse(ApiPaths.invoice(4), {
          'id': 4,
          'client': 1,
          'kind': 'time',
          'status': 'draft',
          'subtotal': '0',
          'tax': '0',
          'total': '0',
          'currency': 'GBP',
          'due_date': null,
          'notes': '',
          'xero_invoice_id': '',
          'xero_status': '',
          'xero_synced_at': null,
          'sent_at': null,
          'paid_at': null,
          'lines': [],
          'created_at': '2026-05-15T09:00:00Z',
          'updated_at': '2026-05-15T09:00:00Z',
        }),
      );
      final inv = await InvoicesRepository(ctx.api).get(4);
      expect(inv.id, 4);
      expect(inv.isSyncedToXero, isFalse);
      expect(inv.lines, isEmpty);
    });
  });

  group('InvoicesRepository.sendToXero', () {
    test('POSTs to /invoices/{id}/send/', () async {
      final ctx = buildApi();
      String? capturedPath;
      when(() => ctx.dio.post<dynamic>(any())).thenAnswer((invocation) async {
        capturedPath = invocation.positionalArguments.first as String;
        return okResponse(capturedPath!, {'detail': 'queued'}, status: 202);
      });
      await InvoicesRepository(ctx.api).sendToXero(9);
      expect(capturedPath, ApiPaths.invoiceSend(9));
    });

    test('400 when Xero not connected becomes ApiException', () async {
      final ctx = buildApi();
      when(() => ctx.dio.post<dynamic>(any())).thenThrow(
        dioError(ApiPaths.invoiceSend(9),
            statusCode: 400, data: {'detail': 'Xero is not connected'}),
      );
      await expectLater(
        InvoicesRepository(ctx.api).sendToXero(9),
        throwsA(isA<ApiException>().having((e) => e.statusCode, 'status', 400)),
      );
    });
  });

  Map<String, dynamic> invoiceJson({
    int id = 99,
    String status = 'draft',
    List<Map<String, dynamic>> lines = const [],
  }) =>
      {
        'id': id,
        'client': 3,
        'kind': 'one_off',
        'status': status,
        'subtotal': '0',
        'tax': '0',
        'total': '0',
        'currency': 'GBP',
        'due_date': null,
        'notes': '',
        'xero_invoice_id': '',
        'xero_status': '',
        'xero_synced_at': null,
        'sent_at': null,
        'paid_at': null,
        'lines': lines,
        'created_at': '2026-05-15T09:00:00Z',
        'updated_at': '2026-05-15T09:00:00Z',
      };

  group('InvoicesRepository.create', () {
    test('POSTs client, lines, and optional due_date', () async {
      final ctx = buildApi();
      Map<String, dynamic>? capturedBody;
      String? capturedPath;
      when(() => ctx.dio.post<dynamic>(any(), data: any(named: 'data')))
          .thenAnswer((inv) async {
        capturedPath = inv.positionalArguments.first as String;
        capturedBody =
            inv.namedArguments[const Symbol('data')] as Map<String, dynamic>;
        return okResponse(capturedPath!, invoiceJson(), status: 201);
      });
      await InvoicesRepository(ctx.api).create(
        clientId: 7,
        lines: [
          {'description': 'Onsite', 'quantity': '1.00', 'unit_amount': '60.00'},
        ],
        dueDate: DateTime(2026, 7, 9),
        notes: 'rush',
      );
      expect(capturedPath, ApiPaths.invoices);
      expect(capturedBody?['client'], 7);
      expect(capturedBody?['due_date'], '2026-07-09');
      expect(capturedBody?['notes'], 'rush');
      expect((capturedBody?['lines'] as List).first['description'], 'Onsite');
    });
  });

  group('InvoicesRepository.update', () {
    test('PATCH with nested lines', () async {
      final ctx = buildApi();
      Map<String, dynamic>? capturedBody;
      String? capturedPath;
      when(() => ctx.dio.patch<dynamic>(any(), data: any(named: 'data')))
          .thenAnswer((inv) async {
        capturedPath = inv.positionalArguments.first as String;
        capturedBody =
            inv.namedArguments[const Symbol('data')] as Map<String, dynamic>;
        return okResponse(capturedPath!, invoiceJson());
      });
      await InvoicesRepository(ctx.api).update(
        12,
        notes: 'revised',
        lines: [
          {
            'id': 4,
            'description': 'x',
            'quantity': '1.00',
            'unit_amount': '10.00',
          },
        ],
      );
      expect(capturedPath, ApiPaths.invoice(12));
      expect(capturedBody?['notes'], 'revised');
      expect((capturedBody?['lines'] as List).first['id'], 4);
    });

    test('clearDueDate sends due_date: null', () async {
      final ctx = buildApi();
      Map<String, dynamic>? capturedBody;
      when(() => ctx.dio.patch<dynamic>(any(), data: any(named: 'data')))
          .thenAnswer((inv) async {
        capturedBody =
            inv.namedArguments[const Symbol('data')] as Map<String, dynamic>;
        return okResponse(ApiPaths.invoice(12), invoiceJson());
      });
      await InvoicesRepository(ctx.api).update(12, clearDueDate: true);
      expect(capturedBody!.containsKey('due_date'), isTrue);
      expect(capturedBody!['due_date'], isNull);
    });
  });

  group('InvoicesRepository.delete', () {
    test('DELETEs the invoice', () async {
      final ctx = buildApi();
      String? capturedPath;
      when(() => ctx.dio.delete<dynamic>(any())).thenAnswer((inv) async {
        capturedPath = inv.positionalArguments.first as String;
        return okResponse(capturedPath!, '', status: 204);
      });
      await InvoicesRepository(ctx.api).delete(15);
      expect(capturedPath, ApiPaths.invoice(15));
    });
  });

  group('InvoicesRepository.setStatus', () {
    test('POSTs target status to /status/', () async {
      final ctx = buildApi();
      String? capturedPath;
      Map<String, dynamic>? capturedBody;
      when(() => ctx.dio.post<dynamic>(any(), data: any(named: 'data')))
          .thenAnswer((inv) async {
        capturedPath = inv.positionalArguments.first as String;
        capturedBody =
            inv.namedArguments[const Symbol('data')] as Map<String, dynamic>;
        return okResponse(capturedPath!, invoiceJson(status: 'sent'));
      });
      final inv =
          await InvoicesRepository(ctx.api).setStatus(8, InvoiceStatus.sent);
      expect(capturedPath, ApiPaths.invoiceStatus(8));
      expect(capturedBody?['status'], 'sent');
      expect(inv.status, InvoiceStatus.sent);
    });
  });

  group('InvoicesRepository.generateFromTime', () {
    test('POSTs the client id', () async {
      final ctx = buildApi();
      String? capturedPath;
      Map<String, dynamic>? capturedBody;
      when(() => ctx.dio.post<dynamic>(any(), data: any(named: 'data')))
          .thenAnswer((inv) async {
        capturedPath = inv.positionalArguments.first as String;
        capturedBody =
            inv.namedArguments[const Symbol('data')] as Map<String, dynamic>;
        return okResponse(capturedPath!, invoiceJson(), status: 201);
      });
      await InvoicesRepository(ctx.api).generateFromTime(7);
      expect(capturedPath, ApiPaths.invoicesGenerateFromTime);
      expect(capturedBody?['client'], 7);
    });

    test('400 when no unbilled entries surfaces ApiException', () async {
      final ctx = buildApi();
      when(() => ctx.dio.post<dynamic>(any(), data: any(named: 'data')))
          .thenThrow(
        dioError(ApiPaths.invoicesGenerateFromTime,
            statusCode: 400, data: {'detail': 'no unbilled time entries'}),
      );
      await expectLater(
        InvoicesRepository(ctx.api).generateFromTime(7),
        throwsA(isA<ApiException>().having((e) => e.statusCode, 'status', 400)),
      );
    });
  });
}
