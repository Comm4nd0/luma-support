import 'package:dio/dio.dart';

import '../models/site_visit.dart';
import '../services/api_client.dart';
import '../services/api_paths.dart';

class SiteVisitsRepository {
  SiteVisitsRepository(this._api);

  final ApiClient _api;

  Future<List<SiteVisit>> list({int? clientId, bool openOnly = false}) async {
    try {
      final res = await _api.dio.get<dynamic>(
        ApiPaths.siteVisits,
        queryParameters: {
          if (clientId != null) 'client': clientId,
        },
      );
      final data = res.data;
      final rows = (data is Map && data.containsKey('results'))
          ? data['results'] as List
          : data as List;
      final visits = rows
          .map((r) => SiteVisit.fromJson(r as Map<String, dynamic>))
          .toList();
      return openOnly ? visits.where((v) => v.isOpen).toList() : visits;
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<SiteVisit> start(int clientId, {double? lat, double? lon}) async {
    try {
      final res = await _api.dio.post<dynamic>(
        ApiPaths.siteVisitStart(clientId),
        data: {
          if (lat != null) 'lat': lat,
          if (lon != null) 'lon': lon,
        },
      );
      return SiteVisit.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<SiteVisit> end(
    int visitId, {
    int? ticketId,
    String? notes,
    double? lat,
    double? lon,
  }) async {
    try {
      final res = await _api.dio.post<dynamic>(
        ApiPaths.siteVisitEnd(visitId),
        data: {
          if (ticketId != null) 'ticket': ticketId,
          if (notes != null && notes.isNotEmpty) 'notes': notes,
          if (lat != null) 'lat': lat,
          if (lon != null) 'lon': lon,
        },
      );
      return SiteVisit.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}
