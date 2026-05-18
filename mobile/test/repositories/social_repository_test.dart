import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:luma_support_mobile/src/repositories/social_repository.dart';
import 'package:luma_support_mobile/src/services/api_paths.dart';

import '../helpers/mock_dio.dart';

void main() {
  setUpAll(registerMockFallbacks);

  group('SocialRepository.listAccounts', () {
    test('parses paginated DRF envelope', () async {
      final ctx = buildApi();
      when(() => ctx.dio.get<dynamic>(any())).thenAnswer((_) async =>
          okResponse(ApiPaths.socialAccounts, {
            'count': 1,
            'results': [
              {
                'id': 1,
                'platform': 'linkedin_page',
                'platform_display': 'LinkedIn Page',
                'display_name': 'Luma',
                'health_status': 'ok',
                'followers': 500,
                'followers_delta_7d': 12,
                'days_since_last_post': 3,
                'last_error': '',
              }
            ],
          }));
      final accounts = await SocialRepository(ctx.api).listAccounts();
      expect(accounts, hasLength(1));
      expect(accounts.first.platform, 'linkedin_page');
      expect(accounts.first.followers, 500);
      expect(accounts.first.followersDelta7d, 12);
      expect(accounts.first.daysSinceLastPost, 3);
      expect(accounts.first.isHealthy, isTrue);
    });
  });

  group('SocialRepository.listInbox', () {
    test('passes status filter and parses items', () async {
      final ctx = buildApi();
      Map<String, dynamic>? captured;
      when(() => ctx.dio.get<dynamic>(
            any(),
            queryParameters: any(named: 'queryParameters'),
          )).thenAnswer((invocation) async {
        captured = invocation.namedArguments[const Symbol('queryParameters')]
            as Map<String, dynamic>;
        return okResponse(ApiPaths.socialInbox, {
          'results': [
            {
              'id': 9,
              'account_platform': 'facebook_page',
              'account_display': 'Luma FB',
              'kind': 'dm',
              'kind_display': 'Direct message',
              'author_handle': 'alice',
              'author_display': 'Alice',
              'preview': 'Fix wifi?',
              'permalink': 'https://example.com/9',
              'received_at': '2026-05-18T12:00:00Z',
              'status': 'open',
              'converted_ticket': null,
            }
          ],
        });
      });
      final items = await SocialRepository(ctx.api).listInbox();
      expect(captured?['status'], 'open');
      expect(items, hasLength(1));
      expect(items.first.kind, 'dm');
      expect(items.first.authorHandle, 'alice');
    });
  });

  group('SocialRepository.convertToTicket', () {
    test('returns the new ticket id from the response', () async {
      final ctx = buildApi();
      when(() => ctx.dio.post<dynamic>(
            any(),
            data: any(named: 'data'),
            options: any(named: 'options'),
          )).thenAnswer((_) async => okResponse(
                ApiPaths.socialInboxConvert(9),
                {'id': 9, 'status': 'converted', 'ticket_id': 42},
              ));
      final ticketId = await SocialRepository(ctx.api).convertToTicket(9);
      expect(ticketId, 42);
    });

    test('sends client_id when supplied', () async {
      final ctx = buildApi();
      dynamic capturedData;
      when(() => ctx.dio.post<dynamic>(
            any(),
            data: any(named: 'data'),
            options: any(named: 'options'),
          )).thenAnswer((invocation) async {
        capturedData = invocation.namedArguments[const Symbol('data')];
        return okResponse(ApiPaths.socialInboxConvert(9), {'ticket_id': 7});
      });
      await SocialRepository(ctx.api).convertToTicket(9, clientId: 3);
      expect(capturedData, {'client_id': 3});
    });
  });
}
