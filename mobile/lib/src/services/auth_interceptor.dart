import 'package:dio/dio.dart';

import 'auth_service.dart';

/// On 401: try to refresh the access token, then replay the original
/// request. If refresh fails the user is logged out (cleared tokens) and
/// the original error is rethrown so the UI routes back to /login.
///
/// The retry is guarded by `_isRetry` on the request options so we never
/// loop forever on a refresh endpoint that itself returns 401.
class AuthInterceptor extends Interceptor {
  AuthInterceptor(this._auth, this._dio);

  final AuthService _auth;
  final Dio _dio;

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    final token = _auth.accessToken;
    if (token != null && options.headers['Authorization'] == null) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    final req = err.requestOptions;
    final alreadyRetried = req.extra['_isRetry'] == true;
    if (err.response?.statusCode != 401 || alreadyRetried) {
      return handler.next(err);
    }

    final ok = await _auth.refresh();
    if (!ok) {
      return handler.next(err);
    }

    req.extra['_isRetry'] = true;
    req.headers['Authorization'] = 'Bearer ${_auth.accessToken}';
    try {
      final retry = await _dio.fetch<dynamic>(req);
      return handler.resolve(retry);
    } on DioException catch (retryErr) {
      return handler.next(retryErr);
    }
  }
}
