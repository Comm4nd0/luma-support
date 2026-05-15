import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:luma_support_mobile/src/repositories/knowledge_repository.dart';
import 'package:luma_support_mobile/src/services/api_paths.dart';

import '../helpers/mock_dio.dart';

void main() {
  setUpAll(registerMockFallbacks);

  test('list() parses articles', () async {
    final ctx = buildApi();
    when(() => ctx.dio.get<dynamic>(
          any(),
          queryParameters: any(named: 'queryParameters'),
        )).thenAnswer((_) async => okResponse(ApiPaths.articles, {
          'results': [
            {
              'id': 1,
              'title': 'Reset a UniFi AP',
              'slug': 'reset-unifi-ap',
              'content': '1. Hold the reset button.',
              'category': 'network',
              'client_visible': true,
              'published_at': '2026-04-01T00:00:00Z',
            }
          ]
        }));
    final items = await KnowledgeRepository(ctx.api).list();
    expect(items, hasLength(1));
    expect(items.first.slug, 'reset-unifi-ap');
    expect(items.first.clientVisible, true);
  });

  test('list(q: term) sends search query', () async {
    final ctx = buildApi();
    Map<String, dynamic>? captured;
    when(() => ctx.dio.get<dynamic>(
          any(),
          queryParameters: any(named: 'queryParameters'),
        )).thenAnswer((invocation) async {
      captured = invocation.namedArguments[const Symbol('queryParameters')]
          as Map<String, dynamic>;
      return okResponse(ApiPaths.articles, {'results': []});
    });
    await KnowledgeRepository(ctx.api).list(q: 'wifi');
    expect(captured?['search'], 'wifi');
  });
}
