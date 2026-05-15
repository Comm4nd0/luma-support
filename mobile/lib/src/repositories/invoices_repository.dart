import 'package:dio/dio.dart';

import '../models/invoice.dart';
import '../services/api_client.dart';
import '../services/api_paths.dart';

class InvoicesRepository {
  InvoicesRepository(this._api);

  final ApiClient _api;

  Future<List<Invoice>> list({
    int? clientId,
    InvoiceStatus? status,
    String? search,
  }) async {
    try {
      final res = await _api.dio.get<dynamic>(
        ApiPaths.invoices,
        queryParameters: {
          if (clientId != null) 'client': clientId,
          if (status != null && status != InvoiceStatus.unknown)
            'status': invoiceStatusToWire(status),
          if (search != null && search.isNotEmpty) 'search': search,
        },
      );
      final data = res.data;
      final rows = (data is Map && data.containsKey('results'))
          ? data['results'] as List
          : data as List;
      return rows
          .map((r) => Invoice.fromJson(r as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Invoice> get(int id) async {
    try {
      final res = await _api.dio.get<dynamic>(ApiPaths.invoice(id));
      return Invoice.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// POST /invoices/{id}/send/ — queues the push to Xero. Server returns
  /// 202 on success, or 400 if Xero is not connected / already pushed.
  Future<void> sendToXero(int id) async {
    try {
      await _api.dio.post<dynamic>(ApiPaths.invoiceSend(id));
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// POST /invoices/ — creates a draft one-off invoice with the given lines.
  /// `lines` is a list of [InvoiceLine.toWritePayload] maps (id omitted).
  Future<Invoice> create({
    required int clientId,
    required List<Map<String, dynamic>> lines,
    DateTime? dueDate,
    String? notes,
    String? currency,
  }) async {
    try {
      final body = <String, dynamic>{
        'client': clientId,
        'lines': lines,
        if (dueDate != null)
          'due_date':
              '${dueDate.year.toString().padLeft(4, '0')}-${dueDate.month.toString().padLeft(2, '0')}-${dueDate.day.toString().padLeft(2, '0')}',
        if (notes != null && notes.isNotEmpty) 'notes': notes,
        if (currency != null && currency.isNotEmpty) 'currency': currency,
      };
      final res = await _api.dio.post<dynamic>(ApiPaths.invoices, data: body);
      return Invoice.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// PATCH /invoices/{id}/ — updates invoice-level fields and, when `lines`
  /// is provided, replaces the line set (server-side diff by `id`).
  /// Only draft invoices are editable; non-draft returns 400.
  Future<Invoice> update(
    int id, {
    DateTime? dueDate,
    bool clearDueDate = false,
    String? notes,
    List<Map<String, dynamic>>? lines,
  }) async {
    try {
      final body = <String, dynamic>{
        if (clearDueDate)
          'due_date': null
        else if (dueDate != null)
          'due_date':
              '${dueDate.year.toString().padLeft(4, '0')}-${dueDate.month.toString().padLeft(2, '0')}-${dueDate.day.toString().padLeft(2, '0')}',
        if (notes != null) 'notes': notes,
        if (lines != null) 'lines': lines,
      };
      final res =
          await _api.dio.patch<dynamic>(ApiPaths.invoice(id), data: body);
      return Invoice.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// DELETE /invoices/{id}/ — only allowed on draft invoices server-side.
  Future<void> delete(int id) async {
    try {
      await _api.dio.delete<dynamic>(ApiPaths.invoice(id));
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// POST /invoices/{id}/status/ — manual status transition.
  /// Allowed: draft→sent, draft→voided, sent→voided. Other transitions
  /// (notably →paid) are owned by Xero/payment-sync and return 400 here.
  Future<Invoice> setStatus(int id, InvoiceStatus target) async {
    try {
      final res = await _api.dio.post<dynamic>(
        ApiPaths.invoiceStatus(id),
        data: {'status': invoiceStatusToWire(target)},
      );
      return Invoice.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// POST /invoices/generate-from-time/ — bundle unbilled time entries for
  /// `clientId` into a new draft time invoice. Returns 400 when there are
  /// no unbilled entries.
  Future<Invoice> generateFromTime(int clientId) async {
    try {
      final res = await _api.dio.post<dynamic>(
        ApiPaths.invoicesGenerateFromTime,
        data: {'client': clientId},
      );
      return Invoice.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}
