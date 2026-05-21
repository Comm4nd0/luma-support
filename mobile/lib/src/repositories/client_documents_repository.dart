import 'dart:io';

import 'package:dio/dio.dart';

import '../models/client_document.dart';
import '../services/api_client.dart';
import '../services/api_paths.dart';

class ClientDocumentsRepository {
  ClientDocumentsRepository(this._api);

  final ApiClient _api;

  Future<List<ClientDocument>> list({int? clientId}) async {
    try {
      final res = await _api.dio.get<dynamic>(
        ApiPaths.clientDocuments,
        queryParameters: {if (clientId != null) 'client': clientId},
      );
      final data = res.data;
      final rows = (data is Map && data.containsKey('results'))
          ? data['results'] as List
          : data as List;
      return rows
          .map((r) => ClientDocument.fromJson(r as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<ClientDocument> upload({
    required int clientId,
    required String title,
    required File file,
    String kind = 'other',
    bool clientVisible = true,
  }) async {
    try {
      final form = FormData.fromMap({
        'client': clientId,
        'title': title,
        'kind': kind,
        'client_visible': clientVisible,
        'file': await MultipartFile.fromFile(file.path),
      });
      final res = await _api.dio.post<dynamic>(
        ApiPaths.clientDocuments,
        data: form,
        options: Options(contentType: 'multipart/form-data'),
      );
      return ClientDocument.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> delete(int id) async {
    try {
      await _api.dio.delete<dynamic>('${ApiPaths.clientDocuments}$id/');
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}
