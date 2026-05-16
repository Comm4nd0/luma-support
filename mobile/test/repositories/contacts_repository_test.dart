import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:luma_support_mobile/src/repositories/contacts_repository.dart';
import 'package:luma_support_mobile/src/services/api_paths.dart';

import '../helpers/mock_dio.dart';

void main() {
  setUpAll(registerMockFallbacks);

  group('ContactsRepository.create', () {
    test('POSTs to /clients/contacts/ with the right payload', () async {
      final ctx = buildApi();
      Map<String, dynamic>? captured;
      when(() => ctx.dio.post<dynamic>(
            any(),
            data: any(named: 'data'),
          )).thenAnswer((invocation) async {
        captured = invocation.namedArguments[const Symbol('data')]
            as Map<String, dynamic>;
        return okResponse(ApiPaths.contacts, {
          'id': 11,
          'client': 1,
          'name': 'Jess',
          'email': 'j@acme.test',
          'phone': '',
          'title': 'IT',
          'is_primary': false,
        });
      });

      final contact = await ContactsRepository(ctx.api).create(
        clientId: 1,
        name: 'Jess',
        email: 'j@acme.test',
        title: 'IT',
      );

      expect(contact.id, 11);
      expect(contact.name, 'Jess');
      expect(captured!['client'], 1);
      expect(captured!['name'], 'Jess');
      expect(captured!['is_primary'], false);
      verify(() => ctx.dio.post<dynamic>(
            ApiPaths.contacts,
            data: any(named: 'data'),
          )).called(1);
    });
  });

  group('ContactsRepository.delete', () {
    test('DELETEs /clients/contacts/<id>/', () async {
      final ctx = buildApi();
      when(() => ctx.dio.delete<dynamic>(any()))
          .thenAnswer((_) async => okResponse('${ApiPaths.contacts}5/', null));

      await ContactsRepository(ctx.api).delete(5);
      verify(() => ctx.dio.delete<dynamic>('${ApiPaths.contacts}5/')).called(1);
    });
  });
}
