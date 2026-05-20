import 'package:dio/dio.dart';

import '../models/lead.dart';
import '../models/lead_activity.dart';
import '../services/api_client.dart';
import '../services/api_paths.dart';

class LeadsRepository {
  LeadsRepository(this._api);

  final ApiClient _api;

  Future<List<Lead>> list({String? stage, String? source}) async {
    try {
      final qp = <String, dynamic>{};
      if (stage != null && stage.isNotEmpty) qp['stage'] = stage;
      if (source != null && source.isNotEmpty) qp['source'] = source;
      final res = await _api.dio.get<dynamic>(
        ApiPaths.leads,
        queryParameters: qp.isEmpty ? null : qp,
      );
      final data = res.data;
      final rows = (data is Map && data.containsKey('results'))
          ? data['results'] as List
          : data as List;
      return rows
          .map((r) => Lead.fromJson(r as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Lead> get(int id) async {
    try {
      final res = await _api.dio.get<dynamic>(ApiPaths.lead(id));
      return Lead.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Lead> create(Map<String, dynamic> body) async {
    try {
      final res = await _api.dio.post<dynamic>(ApiPaths.leads, data: body);
      return Lead.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Lead> update(int id, Map<String, dynamic> body) async {
    try {
      final res =
          await _api.dio.patch<dynamic>(ApiPaths.lead(id), data: body);
      return Lead.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Lead> advance(int id, String stage, {String lostReason = ''}) async {
    try {
      final res = await _api.dio.post<dynamic>(
        ApiPaths.leadAdvance(id),
        data: {'stage': stage, if (lostReason.isNotEmpty) 'lost_reason': lostReason},
      );
      return Lead.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<int> convert(int id) async {
    try {
      final res = await _api.dio.post<dynamic>(ApiPaths.leadConvert(id));
      final data = res.data as Map<String, dynamic>;
      return data['client_id'] as int;
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<LeadActivity> addActivity(int id, String kind, String body) async {
    try {
      final res = await _api.dio.post<dynamic>(
        ApiPaths.leadActivities(id),
        data: {'kind': kind, 'body': body},
      );
      return LeadActivity.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}
