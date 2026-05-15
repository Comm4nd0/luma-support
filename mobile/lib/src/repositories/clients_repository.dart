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
}
