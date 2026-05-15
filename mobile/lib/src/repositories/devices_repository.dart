import 'dart:io' show Platform;

import 'package:dio/dio.dart';

import '../services/api_client.dart';
import '../services/api_paths.dart';

class DevicesRepository {
  DevicesRepository(this._api);

  final ApiClient _api;

  /// Upsert a device token at the backend so push notifications can target
  /// this device. Called on first login and on every `onTokenRefresh`.
  Future<void> register(String token, {String appVersion = ''}) async {
    final platform = Platform.isIOS ? 'ios' : 'android';
    try {
      await _api.dio.post<dynamic>(
        ApiPaths.devices,
        data: {
          'platform': platform,
          'token': token,
          'app_version': appVersion,
        },
      );
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}
