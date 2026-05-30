import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:luma_support_mobile/src/repositories/me_repository.dart';
import 'package:luma_support_mobile/src/services/api_paths.dart';

import '../helpers/mock_dio.dart';

void main() {
  setUpAll(registerMockFallbacks);

  group('MeRepository.setupTotp', () {
    test('returns the secret + otpauth URI', () async {
      final ctx = buildApi();
      when(() => ctx.dio.post<dynamic>(any())).thenAnswer(
        (_) async => okResponse(ApiPaths.totpSetup, {
          'secret': 'ABCD1234EFGH5678',
          'otpauth_uri':
              'otpauth://totp/Luma:eng@luma.test?secret=ABCD1234EFGH5678',
        }),
      );
      final setup = await MeRepository(ctx.api).setupTotp();
      expect(setup.secret, 'ABCD1234EFGH5678');
      expect(setup.otpauthUri, startsWith('otpauth://totp/'));
    });
  });

  group('MeRepository.confirmTotp', () {
    test('POSTs the code and returns recovery codes', () async {
      final ctx = buildApi();
      Map<String, dynamic>? captured;
      when(() => ctx.dio.post<dynamic>(
            any(),
            data: any(named: 'data'),
          )).thenAnswer((invocation) async {
        captured = invocation.namedArguments[const Symbol('data')]
            as Map<String, dynamic>;
        return okResponse(ApiPaths.totpConfirm, {
          'enabled': true,
          'recovery_codes': ['aaaa-bbbb', 'cccc-dddd'],
        });
      });
      final codes = await MeRepository(ctx.api).confirmTotp('123456');
      expect(captured?['code'], '123456');
      expect(codes, ['aaaa-bbbb', 'cccc-dddd']);
    });
  });
}
