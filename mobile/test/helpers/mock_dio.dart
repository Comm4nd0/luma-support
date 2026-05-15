import 'package:dio/dio.dart';
import 'package:mocktail/mocktail.dart';

import 'package:luma_support_mobile/src/services/api_client.dart';

/// Mock Dio used across repository unit tests.
class MockDio extends Mock implements Dio {}

/// Once-only fallback registration so `any()` and named params don't throw
/// MissingStubError when mocktail tries to materialise a default value.
void registerMockFallbacks() {
  registerFallbackValue(RequestOptions(path: ''));
  registerFallbackValue(<String, dynamic>{});
  registerFallbackValue(Options());
}

/// Convenience for building an [ApiClient] backed by a [MockDio].
({MockDio dio, ApiClient api}) buildApi() {
  final dio = MockDio();
  final api = ApiClient.withDio(dio);
  return (dio: dio, api: api);
}

/// Wrap a JSON body in a [Response] keyed off the request path.
Response<dynamic> okResponse(String path, dynamic data, {int status = 200}) {
  return Response<dynamic>(
    data: data,
    statusCode: status,
    requestOptions: RequestOptions(path: path),
  );
}

DioException dioError(String path, {int statusCode = 500, dynamic data}) {
  final req = RequestOptions(path: path);
  return DioException(
    requestOptions: req,
    response: Response<dynamic>(
      requestOptions: req,
      statusCode: statusCode,
      data: data,
    ),
    type: DioExceptionType.badResponse,
  );
}
