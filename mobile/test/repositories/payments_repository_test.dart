import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:luma_support_mobile/src/repositories/payments_repository.dart';
import 'package:luma_support_mobile/src/services/api_paths.dart';

import '../helpers/mock_dio.dart';

void main() {
  setUpAll(registerMockFallbacks);

  test('parses paginated DRF response into Payments', () async {
    final ctx = buildApi();
    when(() => ctx.dio.get<dynamic>(
          any(),
          queryParameters: any(named: 'queryParameters'),
        )).thenAnswer((_) async => okResponse(
          ApiPaths.payments,
          {
            'count': 1,
            'results': [
              {
                'id': 2,
                'invoice': 11,
                'xero_payment_id': 'XP-100',
                'amount': '120.00',
                'paid_at': '2026-05-15T12:00:00Z',
                'reference': 'BACS-9',
                'created_at': '2026-05-15T12:01:00Z',
              },
            ],
          },
        ));
    final payments = await PaymentsRepository(ctx.api).list();
    expect(payments, hasLength(1));
    expect(payments.first.amount, 120.0);
    expect(payments.first.invoiceId, 11);
    expect(payments.first.reference, 'BACS-9');
  });

  test('forwards invoice filter', () async {
    final ctx = buildApi();
    Map<String, dynamic>? captured;
    when(() => ctx.dio.get<dynamic>(
          any(),
          queryParameters: any(named: 'queryParameters'),
        )).thenAnswer((invocation) async {
      captured = invocation.namedArguments[const Symbol('queryParameters')]
          as Map<String, dynamic>;
      return okResponse(ApiPaths.payments, {'results': []});
    });
    await PaymentsRepository(ctx.api).list(invoiceId: 11);
    expect(captured?['invoice'], 11);
  });
}
