import 'package:dio/dio.dart';

import 'auth_interceptor.dart';
import 'auth_service.dart';
import 'config.dart';

/// Thin Dio wrapper. Repositories take an [ApiClient] and call [dio]
/// directly — that way unit tests can swap a fake Dio in without reaching
/// into every repository.
///
/// When [dio] is omitted we build a production Dio and wire the auth
/// interceptor onto it. When tests pass one in we leave it alone — they
/// own the interceptor stack.
class ApiClient {
  ApiClient(AuthService auth, {Dio? dio}) : dio = dio ?? _buildDio(auth);

  /// Used by widget/unit tests that already have a configured Dio.
  ApiClient.withDio(this.dio);

  final Dio dio;

  static Dio _buildDio(AuthService auth) {
    final dio = Dio(
      BaseOptions(
        baseUrl: kApiBase,
        connectTimeout: const Duration(seconds: 15),
        receiveTimeout: const Duration(seconds: 30),
        headers: {'Content-Type': 'application/json'},
        responseType: ResponseType.json,
      ),
    );
    dio.interceptors.add(AuthInterceptor(auth, dio));
    return dio;
  }
}

/// Single error type carrying status + parsed DRF error payload, raised
/// by repositories so screens have one thing to catch.
class ApiException implements Exception {
  ApiException(this.statusCode, this.body, [this.message]);

  final int? statusCode;
  final dynamic body;
  final String? message;

  @override
  String toString() => message ?? 'API error ($statusCode): $body';

  static ApiException fromDio(DioException e) {
    return ApiException(
      e.response?.statusCode,
      e.response?.data,
      e.message,
    );
  }
}
