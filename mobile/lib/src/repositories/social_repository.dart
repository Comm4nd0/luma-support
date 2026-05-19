import 'package:dio/dio.dart';

import '../models/social_account.dart';
import '../models/social_inbox_item.dart';
import '../services/api_client.dart';
import '../services/api_paths.dart';

class SocialRepository {
  SocialRepository(this._api);
  final ApiClient _api;

  Future<List<SocialAccountSummary>> listAccounts() async {
    final res = await _api.dio.get<dynamic>(ApiPaths.socialAccounts);
    final results = _resultsFrom(res.data);
    return results
        .whereType<Map<String, dynamic>>()
        .map(SocialAccountSummary.fromJson)
        .toList();
  }

  Future<List<SocialInboxItem>> listInbox({String status = 'open'}) async {
    final res = await _api.dio.get<dynamic>(
      ApiPaths.socialInbox,
      queryParameters: {'status': status},
    );
    final results = _resultsFrom(res.data);
    return results
        .whereType<Map<String, dynamic>>()
        .map(SocialInboxItem.fromJson)
        .toList();
  }

  Future<SocialInboxItem> dismiss(int id) async {
    final res = await _api.dio.post<dynamic>(ApiPaths.socialInboxDismiss(id));
    return SocialInboxItem.fromJson(res.data as Map<String, dynamic>);
  }

  /// Converts an inbox item into a Ticket. Returns the new ticket id;
  /// the server falls back to creating a "Social lead:" Client when
  /// no `clientId` is supplied.
  Future<int> convertToTicket(int id, {int? clientId}) async {
    final res = await _api.dio.post<dynamic>(
      ApiPaths.socialInboxConvert(id),
      data: clientId == null ? {} : {'client_id': clientId},
      options: Options(contentType: Headers.jsonContentType),
    );
    final body = res.data as Map<String, dynamic>;
    return (body['ticket_id'] as num).toInt();
  }

  /// DRF returns a paginated `{count, next, previous, results}` envelope.
  /// Strip it for callers that just want the list.
  List<dynamic> _resultsFrom(dynamic body) {
    if (body is List) return body;
    if (body is Map<String, dynamic> && body['results'] is List) {
      return body['results'] as List<dynamic>;
    }
    return const [];
  }
}
