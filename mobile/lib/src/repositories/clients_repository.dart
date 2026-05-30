import 'dart:io';

import 'package:dio/dio.dart';
import 'package:path_provider/path_provider.dart';

import '../models/client.dart';
import '../models/timeline_event.dart';
import '../services/api_client.dart';
import '../services/api_paths.dart';

class ClientsRepository {
  ClientsRepository(this._api);

  final ApiClient _api;

  Future<List<Client>> list() async {
    try {
      final res = await _api.dio.get<dynamic>(ApiPaths.clients);
      final data = res.data;
      final rows = (data is Map && data.containsKey('results'))
          ? data['results'] as List
          : data as List;
      return rows
          .map((r) => Client.fromJson(r as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Client> get(int id) async {
    try {
      final res = await _api.dio.get<dynamic>(ApiPaths.client(id));
      return Client.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// Fetch the component breakdown of a client's health score — same
  /// shape the portal renders in the expandable panel.
  Future<ClientHealth> health(int id) async {
    try {
      final res = await _api.dio.get<dynamic>(ApiPaths.clientHealth(id));
      return ClientHealth.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// Unified per-client communication log — tickets, notes, quotes,
  /// invoices, lead activity. Parity with the portal ClientTimelineView.
  Future<List<TimelineEvent>> timeline(int id) async {
    try {
      final res = await _api.dio.get<dynamic>(ApiPaths.clientTimeline(id));
      return (res.data as List)
          .whereType<Map<String, dynamic>>()
          .map(TimelineEvent.fromJson)
          .toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// Download the monthly support PDF (defaults to the current month) to a
  /// temp file and return its path so the caller can open / share it.
  Future<String> downloadMonthlyReport(int id, {int? year, int? month}) async {
    try {
      final res = await _api.dio.get<List<int>>(
        ApiPaths.clientMonthlyReport(id),
        queryParameters: {
          if (year != null) 'year': year,
          if (month != null) 'month': month,
        },
        options: Options(responseType: ResponseType.bytes),
      );
      final dir = await getTemporaryDirectory();
      final stamp = year != null && month != null
          ? '$year-${month.toString().padLeft(2, '0')}'
          : 'latest';
      final file = File('${dir.path}/client-$id-$stamp.pdf');
      await file.writeAsBytes(res.data ?? const <int>[], flush: true);
      return file.path;
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Client> create(Map<String, dynamic> body) async {
    try {
      final res = await _api.dio.post<dynamic>(ApiPaths.clients, data: body);
      return Client.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Client> update(int id, Map<String, dynamic> body) async {
    try {
      final res = await _api.dio.patch<dynamic>(
        ApiPaths.client(id),
        data: body,
      );
      return Client.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}

class ClientHealth {
  const ClientHealth({
    required this.score,
    required this.band,
    required this.csat,
    required this.openTickets,
    required this.overdueInvoices,
    required this.systemsOkPct,
    required this.reasons,
  });

  final int score;
  final String band; // good | watch | at_risk
  final double? csat;
  final int openTickets;
  final int overdueInvoices;
  final double? systemsOkPct; // 0..1
  final List<String> reasons;

  factory ClientHealth.fromJson(Map<String, dynamic> json) => ClientHealth(
        score: (json['score'] as num?)?.toInt() ?? 0,
        band: json['band'] as String? ?? 'good',
        csat: (json['csat'] as num?)?.toDouble(),
        openTickets: (json['open_tickets'] as num?)?.toInt() ?? 0,
        overdueInvoices: (json['overdue_invoices'] as num?)?.toInt() ?? 0,
        systemsOkPct: (json['systems_ok_pct'] as num?)?.toDouble(),
        reasons: ((json['reasons'] as List?) ?? const [])
            .map((e) => e.toString())
            .toList(),
      );
}
