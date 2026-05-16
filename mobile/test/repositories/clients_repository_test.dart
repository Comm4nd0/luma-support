import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:luma_support_mobile/src/repositories/clients_repository.dart';
import 'package:luma_support_mobile/src/services/api_paths.dart';

import '../helpers/mock_dio.dart';

void main() {
  setUpAll(registerMockFallbacks);

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
