import 'package:dio/dio.dart';

import '../models/referral_code.dart';
import '../services/api_client.dart';
import '../services/api_paths.dart';

class ReferralsRepository {
  ReferralsRepository(this._api);

  final ApiClient _api;

  Future<ReferralCode> myCode() async {
    try {
      final res = await _api.dio.get<dynamic>(ApiPaths.myReferralCode);
      return ReferralCode.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}
