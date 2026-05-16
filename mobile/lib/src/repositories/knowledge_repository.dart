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

  /// Ask the backend (Claude when available, keyword search otherwise) for
  /// up to 3 KB articles relevant to a ticket draft.
  Future<List<KbSuggestion>> suggest({
    required String subject,
    required String description,
  }) async {
    try {
      final res = await _api.dio.post<dynamic>(
        ApiPaths.articleSuggest,
        data: {'subject': subject, 'description': description},
      );
      final data = res.data as Map<String, dynamic>;
      final raw = (data['suggestions'] as List?) ?? const [];
      return raw
          .map((r) => KbSuggestion.fromJson(r as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}

class KbSuggestion {
  KbSuggestion({
    required this.slug,
    required this.title,
    required this.snippet,
    required this.reason,
  });

  final String slug;
  final String title;
  final String snippet;
  final String reason;

  factory KbSuggestion.fromJson(Map<String, dynamic> json) => KbSuggestion(
        slug: json['slug'] as String? ?? '',
        title: json['title'] as String? ?? '',
        snippet: json['snippet'] as String? ?? '',
        reason: json['reason'] as String? ?? '',
      );
}
