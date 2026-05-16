import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:luma_support_mobile/src/repositories/maintenance_repository.dart';
import 'package:luma_support_mobile/src/services/api_paths.dart';

import '../helpers/mock_dio.dart';

void main() {
  setUpAll(registerMockFallbacks);

  group('MaintenanceRepository.update', () {
    test('PUTs the full schedule payload and returns the parsed model',
        () async {
      final ctx = buildApi();
      Map<String, dynamic>? captured;
      when(() => ctx.dio.put<dynamic>(
            any(),
            data: any(named: 'data'),
          )).thenAnswer((invocation) async {
        captured = invocation.namedArguments[const Symbol('data')]
            as Map<String, dynamic>;
        return okResponse(ApiPaths.maintenanceSchedule(3), {
          'id': 3,
          'client': 1,
          'client_name': 'Acme',
          'cadence': 'monthly',
          'next_run_at': '2026-06-01',
          'template_subject': 'UniFi monthly check',
          'template_description': '',
          'active': true,
          'system': null,
        });
      });

      final updated = await MaintenanceRepository(ctx.api).update(
        3,
        clientId: 1,
        cadence: 'monthly',
        nextRunAt: DateTime.utc(2026, 6, 1),
        templateSubject: 'UniFi monthly check',
      );

      expect(updated.id, 3);
      expect(updated.templateSubject, 'UniFi monthly check');
      expect(captured!['client'], 1);
      expect(captured!['cadence'], 'monthly');
      expect(captured!['next_run_at'], '2026-06-01');
      expect(captured!['active'], true);
      verify(() => ctx.dio.put<dynamic>(
            ApiPaths.maintenanceSchedule(3),
            data: any(named: 'data'),
          )).called(1);
    });
  });
}
