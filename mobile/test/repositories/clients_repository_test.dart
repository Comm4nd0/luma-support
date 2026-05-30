import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:luma_support_mobile/src/repositories/clients_repository.dart';
import 'package:luma_support_mobile/src/services/api_client.dart';
import 'package:luma_support_mobile/src/services/api_paths.dart';

import '../helpers/mock_dio.dart';

void main() {
  setUpAll(registerMockFallbacks);

  group('ClientsRepository.timeline', () {
    test('parses the event list into TimelineEvents', () async {
      final ctx = buildApi();
      when(() => ctx.dio.get<dynamic>(any())).thenAnswer(
        (_) async => okResponse(ApiPaths.clientTimeline(7), [
          {
            'kind': 'ticket',
            'occurred_at': '2026-05-20T09:00:00Z',
            'title': 'Ticket #3: Wi-Fi down',
            'body': 'High · Open',
            'url': '/tickets/3/',
            'pill': 'open',
          },
          {
            'kind': 'invoice',
            'occurred_at': '2026-05-19T09:00:00Z',
            'title': 'Invoice INV-2',
            'body': '',
            'url': '/billing/invoices/2/',
            'pill': 'paid',
          },
        ]),
      );
      final events = await ClientsRepository(ctx.api).timeline(7);
      expect(events, hasLength(2));
      expect(events.first.kind, 'ticket');
      expect(events.first.url, '/tickets/3/');
      expect(events[1].pill, 'paid');
    });

    test('wraps DioException as ApiException', () async {
      final ctx = buildApi();
      when(() => ctx.dio.get<dynamic>(any()))
          .thenThrow(dioError(ApiPaths.clientTimeline(7), statusCode: 403));
      await expectLater(
        ClientsRepository(ctx.api).timeline(7),
        throwsA(isA<ApiException>().having((e) => e.statusCode, 'status', 403)),
      );
    });
  });

  group('ClientsRepository.create', () {
    test('POSTs to /clients/clients/ and returns parsed Client', () async {
      final ctx = buildApi();
      Map<String, dynamic>? captured;
      when(() => ctx.dio.post<dynamic>(
            any(),
            data: any(named: 'data'),
          )).thenAnswer((invocation) async {
        captured = invocation.namedArguments[const Symbol('data')]
            as Map<String, dynamic>;
        return okResponse(ApiPaths.clients, {
          'id': 42,
          'name': 'Acme Ltd',
          'company': 'Acme',
          'email': 'ops@acme.test',
          'phone': '01234',
          'care_plan_tier': 'professional',
          'customer_type': 'business',
        });
      });

      final created = await ClientsRepository(ctx.api).create({
        'name': 'Acme Ltd',
        'company': 'Acme',
        'email': 'ops@acme.test',
        'care_plan_tier': 'professional',
        'customer_type': 'business',
      });

      expect(created.id, 42);
      expect(created.name, 'Acme Ltd');
      expect(created.customerType, 'business');
      expect(captured!['care_plan_tier'], 'professional');
      verify(() => ctx.dio.post<dynamic>(
            ApiPaths.clients,
            data: any(named: 'data'),
          )).called(1);
    });
  });

  group('ClientsRepository.update', () {
    test('PATCHes /clients/clients/<id>/ with the supplied fields', () async {
      final ctx = buildApi();
      when(() => ctx.dio.patch<dynamic>(
            any(),
            data: any(named: 'data'),
          )).thenAnswer((_) async => okResponse(
            ApiPaths.client(7),
            {
              'id': 7,
              'name': 'Renamed',
              'company': 'Acme',
              'care_plan_tier': 'essential',
            },
          ));

      final updated =
          await ClientsRepository(ctx.api).update(7, {'name': 'Renamed'});
      expect(updated.id, 7);
      expect(updated.name, 'Renamed');
      verify(() => ctx.dio.patch<dynamic>(
            ApiPaths.client(7),
            data: any(named: 'data'),
          )).called(1);
    });
  });
}
