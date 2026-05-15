import 'dart:io';

import 'package:dio/dio.dart';

import '../models/ticket.dart';
import '../models/ticket_note.dart';
import '../services/api_client.dart';
import '../services/api_paths.dart';

class TicketsRepository {
  TicketsRepository(this._api);

  final ApiClient _api;

  Future<List<Ticket>> list({String? status, String? priority}) async {
    try {
      final res = await _api.dio.get<dynamic>(
        ApiPaths.tickets,
        queryParameters: {
          if (status != null) 'status': status,
          if (priority != null) 'priority': priority,
        },
      );
      final data = res.data;
      final rows = (data is Map && data.containsKey('results'))
          ? data['results'] as List
          : data as List;
      return rows
          .map((r) => Ticket.fromJson(r as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Ticket> get(int id) async {
    try {
      final res = await _api.dio.get<dynamic>(ApiPaths.ticket(id));
      return Ticket.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Ticket> create(Map<String, dynamic> body) async {
    try {
      final res = await _api.dio.post<dynamic>(ApiPaths.tickets, data: body);
      return Ticket.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> setStatus(int id, TicketStatus status) async {
    try {
      await _api.dio.post<dynamic>(
        ApiPaths.ticketStatus(id),
        data: {'status': statusToWire(status)},
      );
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> logTime(
    int id, {
    required int minutes,
    String description = '',
    bool billable = true,
  }) async {
    try {
      await _api.dio.post<dynamic>(
        ApiPaths.ticketTime(id),
        data: {
          'minutes': minutes,
          'description': description,
          'billable': billable,
        },
      );
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<TicketNote> addNote(int id, String body, {bool internal = false}) async {
    try {
      final res = await _api.dio.post<dynamic>(
        ApiPaths.ticketNotes(id),
        data: {'body': body, 'internal': internal},
      );
      return TicketNote.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> uploadAttachment(int id, File file) async {
    try {
      final form = FormData.fromMap({
        'file': await MultipartFile.fromFile(file.path),
      });
      await _api.dio.post<dynamic>(
        ApiPaths.ticketAttachments(id),
        data: form,
        options: Options(contentType: 'multipart/form-data'),
      );
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}
