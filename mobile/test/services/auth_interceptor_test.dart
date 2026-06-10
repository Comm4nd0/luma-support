import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:luma_support_mobile/src/services/auth_interceptor.dart';
import 'package:luma_support_mobile/src/services/auth_service.dart';

/// Hand-rolled fake auth — avoids flutter_secure_storage in tests.
class FakeAuth extends ChangeNotifier implements AuthService {
  FakeAuth({
    String? access,
    String? refresh,
    this.refreshOutcome = true,
  })  : _access = access,
        _refresh = refresh;

  String? _access;
  String? _refresh;
  bool refreshOutcome;
  int refreshCalls = 0;

  @override
  String? get accessToken => _access;

  @override
  String? get refreshToken => _refresh;

  @override
  bool get isAuthenticated => _access != null;

  @override
  bool get loading => false;

  @override
  Future<bool> refresh() async {
    refreshCalls += 1;
    if (!refreshOutcome) {
      _access = null;
      _refresh = null;
      return false;
    }
    _access = 'access-v2';
    return true;
  }

  @override
  Future<LoginResult> login(
    String email,
    String password, {
    String? totpCode,
    String? recoveryCode,
  }) async =>
      LoginResult.badCredentials;

  @override
  Future<void> logout() async {
    _access = null;
    _refresh = null;
  }
}

void main() {
  Dio buildDio(FakeAuth auth) {
    final dio = Dio(BaseOptions(baseUrl: 'http://test/api/v1'));
    dio.interceptors.add(AuthInterceptor(auth, dio));
    return dio;
  }

  test('attaches Authorization header from the current access token',
      () async {
    final auth = FakeAuth(access: 'access-v1');
    final dio = buildDio(auth);
    // Adapter that just echoes the request headers back as JSON.
    dio.httpClientAdapter = _EchoAdapter();
    final res = await dio.get<dynamic>('/echo');
    expect(res.data['headers']['authorization'], 'Bearer access-v1');
  });

  test('refreshes on 401 and retries the original request once', () async {
    final auth = FakeAuth(access: 'expired', refresh: 'r1');
    final dio = buildDio(auth);
    final adapter = _ScriptedAdapter([
      // First call -> 401
      _Reply(statusCode: 401, body: {'detail': 'expired'}),
      // After refresh, retried with new token -> 200
      _Reply(statusCode: 200, body: {'ok': true}),
    ]);
    dio.httpClientAdapter = adapter;
    final res = await dio.get<dynamic>('/echo');
    expect(res.statusCode, 200);
    expect(auth.refreshCalls, 1);
    // Two adapter hits — the 401 then the retry.
    expect(adapter.calls, 2);
    // Retry carried the refreshed bearer token.
    expect(adapter.lastRequest?.headers['Authorization'], 'Bearer access-v2');
  });

  test('does not retry forever — second 401 surfaces as DioException',
      () async {
    final auth = FakeAuth(access: 'expired', refresh: 'r1');
    final dio = buildDio(auth);
    dio.httpClientAdapter = _ScriptedAdapter([
      _Reply(statusCode: 401, body: {'detail': 'expired'}),
      _Reply(statusCode: 401, body: {'detail': 'still bad'}),
    ]);
    await expectLater(
      dio.get<dynamic>('/echo'),
      throwsA(isA<DioException>()
          .having((e) => e.response?.statusCode, 'status', 401)),
    );
    expect(auth.refreshCalls, 1);
  });

  test('clears tokens when refresh itself fails', () async {
    final auth = FakeAuth(
      access: 'expired',
      refresh: 'r1',
      refreshOutcome: false,
    );
    final dio = buildDio(auth);
    dio.httpClientAdapter =
        _ScriptedAdapter([_Reply(statusCode: 401, body: {})]);
    await expectLater(dio.get<dynamic>('/echo'), throwsA(isA<DioException>()));
    expect(auth.isAuthenticated, false);
  });
}

// -----------------------------------------------------------------------
// Minimal Dio HttpClientAdapter test doubles. Real adapters do socket I/O;
// these just script responses.
// -----------------------------------------------------------------------

class _Reply {
  _Reply({required this.statusCode, required this.body});
  final int statusCode;
  final Object body;
}

class _EchoAdapter implements HttpClientAdapter {
  @override
  void close({bool force = false}) {}

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<List<int>>? requestStream,
    Future<dynamic>? cancelFuture,
  ) async {
    final lowerHeaders = <String, String>{
      for (final entry in options.headers.entries) entry.key.toLowerCase(): '${entry.value}',
    };
    final payload = '{"headers":${_jsonEncode(lowerHeaders)}}';
    return ResponseBody.fromString(
      payload,
      200,
      headers: {
        'content-type': ['application/json'],
      },
    );
  }
}

class _ScriptedAdapter implements HttpClientAdapter {
  _ScriptedAdapter(this._replies);

  final List<_Reply> _replies;
  int calls = 0;
  RequestOptions? lastRequest;

  @override
  void close({bool force = false}) {}

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<List<int>>? requestStream,
    Future<dynamic>? cancelFuture,
  ) async {
    lastRequest = options;
    final reply = _replies[calls.clamp(0, _replies.length - 1)];
    calls += 1;
    return ResponseBody.fromString(
      _jsonEncode(reply.body),
      reply.statusCode,
      headers: {
        'content-type': ['application/json'],
      },
    );
  }
}

String _jsonEncode(Object value) {
  if (value is String) return '"$value"';
  if (value is Map) {
    final entries = value.entries
        .map((e) => '"${e.key}":${_jsonEncode(e.value as Object)}')
        .join(',');
    return '{$entries}';
  }
  if (value is bool || value is num) return '$value';
  return '"$value"';
}
