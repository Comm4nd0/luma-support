import 'package:dio/dio.dart';

import '../models/payment.dart';
import '../services/api_client.dart';
import '../services/api_paths.dart';

class PaymentsRepository {
  PaymentsRepository(this._api);

  final ApiClient _api;

  Future<List<Payment>> list({int? invoiceId}) async {
    try {
      final res = await _api.dio.get<dynamic>(
        ApiPaths.payments,
        queryParameters: {
          if (invoiceId != null) 'invoice': invoiceId,
        },
      );
      final data = res.data;
      final rows = (data is Map && data.containsKey('results'))
          ? data['results'] as List
          : data as List;
      return rows
          .map((r) => Payment.fromJson(r as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}
