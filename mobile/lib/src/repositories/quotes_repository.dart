import 'package:dio/dio.dart';

import '../models/quote.dart';
import '../services/api_client.dart';
import '../services/api_paths.dart';

class QuotesRepository {
  QuotesRepository(this._api);

  final ApiClient _api;

  Future<List<Quote>> list({String? status}) async {
    try {
      final res = await _api.dio.get<dynamic>(
        ApiPaths.quotes,
        queryParameters: (status != null && status.isNotEmpty)
            ? {'status': status}
            : null,
      );
      final data = res.data;
      final rows = (data is Map && data.containsKey('results'))
          ? data['results'] as List
          : data as List;
      return rows
          .map((r) => Quote.fromJson(r as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Quote> get(int id) async {
    try {
      final res = await _api.dio.get<dynamic>(ApiPaths.quote(id));
      return Quote.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Quote> create(Map<String, dynamic> body) async {
    try {
      final res = await _api.dio.post<dynamic>(ApiPaths.quotes, data: body);
      return Quote.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Quote> send(int id) async {
    try {
      final res = await _api.dio.post<dynamic>(ApiPaths.quoteSend(id));
      final body = res.data as Map<String, dynamic>;
      return Quote.fromJson(body['quote'] as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}
