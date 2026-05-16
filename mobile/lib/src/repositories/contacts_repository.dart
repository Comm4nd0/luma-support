import 'package:dio/dio.dart';

import '../models/contact.dart';
import '../services/api_client.dart';
import '../services/api_paths.dart';

class ContactsRepository {
  ContactsRepository(this._api);

  final ApiClient _api;

  Future<Contact> create({
    required int clientId,
    required String name,
    String email = '',
    String phone = '',
    String title = '',
    bool isPrimary = false,
  }) async {
    try {
      final res = await _api.dio.post<dynamic>(
        ApiPaths.contacts,
        data: {
          'client': clientId,
          'name': name,
          'email': email,
          'phone': phone,
          'title': title,
          'is_primary': isPrimary,
        },
      );
      return Contact.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Contact> update(
    int id, {
    required int clientId,
    required String name,
    String email = '',
    String phone = '',
    String title = '',
    bool isPrimary = false,
  }) async {
    try {
      final res = await _api.dio.patch<dynamic>(
        '${ApiPaths.contacts}$id/',
        data: {
          'client': clientId,
          'name': name,
          'email': email,
          'phone': phone,
          'title': title,
          'is_primary': isPrimary,
        },
      );
      return Contact.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> delete(int id) async {
    try {
      await _api.dio.delete<dynamic>('${ApiPaths.contacts}$id/');
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}
