import 'package:dio/dio.dart';

import '../models/maintenance_schedule.dart';
import '../services/api_client.dart';
import '../services/api_paths.dart';

class MaintenanceRepository {
  MaintenanceRepository(this._api);

  final ApiClient _api;

  Future<List<MaintenanceSchedule>> list() async {
    try {
      final res = await _api.dio.get<dynamic>(ApiPaths.maintenanceSchedules);
      final data = res.data;
      final rows = (data is Map && data.containsKey('results'))
          ? data['results'] as List
          : data as List;
      return rows
          .map((r) => MaintenanceSchedule.fromJson(r as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<MaintenanceSchedule> get(int id) async {
    try {
      final res = await _api.dio.get<dynamic>(
        ApiPaths.maintenanceSchedule(id),
      );
      return MaintenanceSchedule.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<MaintenanceSchedule> create({
    required int clientId,
    int? systemId,
    required String cadence,
    required DateTime nextRunAt,
    required String templateSubject,
    String templateDescription = '',
    String priority = '',
    int? defaultAssigneeId,
    bool active = true,
  }) async {
    try {
      final res = await _api.dio.post<dynamic>(
        ApiPaths.maintenanceSchedules,
        data: {
          'client': clientId,
          if (systemId != null) 'system': systemId,
          'cadence': cadence,
          'next_run_at':
              '${nextRunAt.year.toString().padLeft(4, "0")}-${nextRunAt.month.toString().padLeft(2, "0")}-${nextRunAt.day.toString().padLeft(2, "0")}',
          'template_subject': templateSubject,
          'template_description': templateDescription,
          'priority': priority,
          if (defaultAssigneeId != null) 'default_assignee': defaultAssigneeId,
          'active': active,
        },
      );
      return MaintenanceSchedule.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> delete(int id) async {
    try {
      await _api.dio.delete<dynamic>(ApiPaths.maintenanceSchedule(id));
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}
