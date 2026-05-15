import 'package:dio/dio.dart';

import '../models/app_notification.dart';
import '../services/api_client.dart';
import '../services/api_paths.dart';

class NotificationsRepository {
  NotificationsRepository(this._api);

  final ApiClient _api;

  Future<List<AppNotification>> list({bool? unreadOnly}) async {
    try {
      final res = await _api.dio.get<dynamic>(
        ApiPaths.notifications,
        queryParameters: {if (unreadOnly == true) 'read': 'false'},
      );
      final data = res.data;
      final rows = (data is Map && data.containsKey('results'))
          ? data['results'] as List
          : data as List;
      return rows
          .map((r) => AppNotification.fromJson(r as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<int> unreadCount() async {
    try {
      final res = await _api.dio.get<dynamic>(ApiPaths.notificationsUnreadCount);
      return (res.data as Map<String, dynamic>)['count'] as int? ?? 0;
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> markRead(int id) async {
    try {
      await _api.dio.post<dynamic>(ApiPaths.notificationMarkRead(id));
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> markAllRead() async {
    try {
      await _api.dio.post<dynamic>(ApiPaths.notificationsMarkAllRead);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}
