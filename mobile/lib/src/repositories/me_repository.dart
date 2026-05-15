import 'package:dio/dio.dart';

import '../models/user.dart';
import '../services/api_client.dart';
import '../services/api_paths.dart';

class MeRepository {
  MeRepository(this._api);

  final ApiClient _api;

  Future<AppUser> fetch() async {
    try {
      final res = await _api.dio.get<dynamic>(ApiPaths.me);
      return AppUser.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}
