import 'package:dio/dio.dart';

import '../models/audit_log.dart';
import '../services/api_client.dart';
import '../services/api_paths.dart';

class AuditRepository {
  AuditRepository(this._api);

  final ApiClient _api;

  Future<List<AuditLogEntry>> list({String? action, String? actor}) async {
    try {
      final res = await _api.dio.get<dynamic>(
        ApiPaths.auditLogs,
        queryParameters: {
          if (action != null && action.isNotEmpty) 'action': action,
          if (actor != null && actor.isNotEmpty) 'search': actor,
        },
      );
      final data = res.data;
      final rows = (data is Map && data.containsKey('results'))
          ? data['results'] as List
          : data as List;
      return rows
          .map((r) => AuditLogEntry.fromJson(r as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}
