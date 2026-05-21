import 'package:dio/dio.dart';

import '../models/client.dart';
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
