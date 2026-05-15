import 'package:dio/dio.dart';

import '../models/article.dart';
import '../services/api_client.dart';
import '../services/api_paths.dart';

class KnowledgeRepository {
  KnowledgeRepository(this._api);

  final ApiClient _api;

  Future<List<Article>> list({String? q}) async {
    try {
      final res = await _api.dio.get<dynamic>(
        ApiPaths.articles,
        queryParameters: {if (q != null && q.isNotEmpty) 'search': q},
      );
      final data = res.data;
      final rows = (data is Map && data.containsKey('results'))
          ? data['results'] as List
          : data as List;
      return rows
          .map((r) => Article.fromJson(r as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Article> get(String slug) async {
    try {
      final res = await _api.dio.get<dynamic>(ApiPaths.article(slug));
      return Article.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}
