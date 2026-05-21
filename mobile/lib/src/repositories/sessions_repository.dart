import 'package:dio/dio.dart';

import '../services/api_client.dart';

class SessionEntry {
  const SessionEntry({
    required this.id,
    required this.jti,
    required this.createdAt,
    required this.expiresAt,
  });

  final int id;
  final String jti;
  final DateTime? createdAt;
  final DateTime? expiresAt;

  factory SessionEntry.fromJson(Map<String, dynamic> json) => SessionEntry(
        id: json['id'] as int,
        jti: json['jti'] as String? ?? '',
        createdAt: _parse(json['created_at']),
        expiresAt: _parse(json['expires_at']),
      );

  static DateTime? _parse(dynamic v) {
    if (v == null) return null;
    if (v is DateTime) return v;
    return DateTime.tryParse(v.toString());
  }
}

class SessionsRepository {
  SessionsRepository(this._api);
  final ApiClient _api;

  Future<List<SessionEntry>> list() async {
    try {
      final res = await _api.dio.get<dynamic>('/auth/sessions/');
      final body = res.data as Map<String, dynamic>;
      final rows = (body['sessions'] as List?) ?? const [];
      return rows
          .map((r) => SessionEntry.fromJson(r as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> revoke(int sessionId) async {
    try {
      await _api.dio.post<dynamic>('/auth/sessions/$sessionId/revoke/');
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<int> revokeAll() async {
    try {
      final res = await _api.dio.post<dynamic>('/auth/sessions/revoke-all/');
      final body = res.data as Map<String, dynamic>;
      return (body['revoked'] as num?)?.toInt() ?? 0;
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}
