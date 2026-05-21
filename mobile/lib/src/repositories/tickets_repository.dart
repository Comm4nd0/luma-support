import 'dart:io';

import 'package:dio/dio.dart';

import '../models/saved_ticket_filter.dart';
import '../models/social_account.dart';
import '../models/ticket.dart';
import '../models/ticket_note.dart';
import '../models/ticket_tag.dart';
import '../models/ticket_template.dart';
import '../services/api_client.dart';
import '../services/api_paths.dart';

class TicketsRepository {
  TicketsRepository(this._api);

  final ApiClient _api;

  Future<List<Ticket>> list({
    String? status,
    String? priority,
    String? tagSlug,
    Map<String, String>? extra,
  }) async {
    try {
      final params = <String, String>{
        if (status != null) 'status': status,
        if (priority != null) 'priority': priority,
        if (tagSlug != null) 'tag_slug': tagSlug,
        ...?extra,
      };
      final res = await _api.dio.get<dynamic>(
        ApiPaths.tickets,
        queryParameters: params,
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

  Future<List<SavedTicketFilter>> listSavedFilters() async {
    try {
      final res = await _api.dio.get<dynamic>(ApiPaths.savedTicketFilters);
      final data = res.data;
      final rows = (data is Map && data.containsKey('results'))
          ? data['results'] as List
          : data as List;
      return rows
          .map((r) => SavedTicketFilter.fromJson(r as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<SavedTicketFilter> saveFilter({
    required String name,
    required String querystring,
    bool pinned = true,
  }) async {
    try {
      final res = await _api.dio.post<dynamic>(
        ApiPaths.savedTicketFilters,
        data: {
          'name': name,
          'querystring': querystring,
          'pinned': pinned,
        },
      );
      return SavedTicketFilter.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> deleteSavedFilter(int id) async {
    try {
      await _api.dio.delete<dynamic>(ApiPaths.savedTicketFilter(id));
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// Staff-only: Claude-suggested next action per open ticket assigned
  /// to me. Returns ``[{ticket_id, action, reason}, …]``. Empty list
  /// when ANTHROPIC_API_KEY isn't set on the backend.
  Future<List<Map<String, dynamic>>> inboxZero({int limit = 15}) async {
    try {
      final res = await _api.dio.post<dynamic>(
        ApiPaths.inboxZero,
        data: {'limit': limit},
      );
      final body = res.data as Map<String, dynamic>;
      final rows = (body['suggestions'] as List?) ?? const [];
      return rows
          .whereType<Map<String, dynamic>>()
          .map((r) => Map<String, dynamic>.from(r))
          .toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// Staff-only SLA hit-rate summary over ``days``. Returns the raw
  /// payload (totals + by_priority); callers can pick the bits they
  /// want to render.
  Future<Map<String, dynamic>> slaAnalytics({int days = 30}) async {
    try {
      final res = await _api.dio.get<dynamic>(
        ApiPaths.slaAnalyticsApi,
        queryParameters: {'days': days},
      );
      return Map<String, dynamic>.from(res.data as Map);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<List<TicketTag>> listTags() async {
    try {
      final res = await _api.dio.get<dynamic>(ApiPaths.ticketTags);
      final data = res.data;
      final rows = (data is Map && data.containsKey('results'))
          ? data['results'] as List
          : data as List;
      return rows
          .map((r) => TicketTag.fromJson(r as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<TicketTag> createTag({required String name, String? color}) async {
    try {
      final res = await _api.dio.post<dynamic>(
        ApiPaths.ticketTags,
        data: {'name': name, if (color != null) 'color': color},
      );
      return TicketTag.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Ticket> setTags(int id, List<int> tagIds) async {
    try {
      final res = await _api.dio.patch<dynamic>(
        ApiPaths.ticket(id),
        data: {'tag_ids': tagIds},
      );
      return Ticket.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<List<TicketTemplate>> listTemplates() async {
    try {
      final res = await _api.dio.get<dynamic>(ApiPaths.ticketTemplates);
      final data = res.data;
      final rows = (data is Map && data.containsKey('results'))
          ? data['results'] as List
          : data as List;
      return rows
          .map((r) => TicketTemplate.fromJson(r as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// Merge ``sourceId`` into ``targetId`` — moves notes / time /
  /// attachments / tags onto the target and closes the source.
  Future<void> mergeInto(int sourceId, int targetId) async {
    try {
      await _api.dio.post<dynamic>(ApiPaths.ticketMergeInto(sourceId, targetId));
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// Apply one action to many tickets — see TicketViewSet.bulk.
  Future<int> bulk({
    required List<int> ids,
    required String action,
    Object? value,
  }) async {
    try {
      final res = await _api.dio.post<dynamic>(
        ApiPaths.ticketsBulk,
        data: {
          'ids': ids,
          'action': action,
          if (value != null) 'value': value,
        },
      );
      final data = res.data as Map<String, dynamic>;
      return (data['touched'] as num?)?.toInt() ?? 0;
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

  /// Staff-only: ask Claude to draft a KB article from a (typically
  /// resolved) ticket. Returns null when ANTHROPIC_API_KEY isn't
  /// configured on the backend; otherwise a map with ``title`` and
  /// ``content`` keys for the caller to review before publishing.
  Future<Map<String, String>?> promoteToKb(int id) async {
    try {
      final res = await _api.dio.post<dynamic>(ApiPaths.ticketPromoteToKb(id));
      final data = res.data as Map<String, dynamic>;
      final draft = data['draft'];
      if (draft is! Map) return null;
      return {
        'title': (draft['title'] ?? '').toString(),
        'content': (draft['content'] ?? '').toString(),
      };
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// Staff-only: ask Claude for a TL;DR of the ticket thread. Returns
  /// the empty string when ANTHROPIC_API_KEY isn't configured on the
  /// backend. The backend caches per-ticket; pass refresh=true to
  /// regenerate.
  Future<String> summariseThread(int id, {bool refresh = false}) async {
    try {
      final res = await _api.dio.post<dynamic>(
        ApiPaths.ticketSummarise(id),
        data: {'refresh': refresh},
      );
      final data = res.data as Map<String, dynamic>;
      return data['summary'] as String? ?? '';
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// Staff-only: ask Claude for a draft reply. Returns the empty string
  /// when ANTHROPIC_API_KEY isn't configured on the backend.
  Future<String> draftReply(int id) async {
    try {
      final res = await _api.dio.post<dynamic>(ApiPaths.ticketDraftReply(id));
      final data = res.data as Map<String, dynamic>;
      return data['draft'] as String? ?? '';
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// Staff-only KPI bundle for the engineer dashboard (parity with the
  /// portal dashboard cards).
  Future<DashboardStats> dashboardStats() async {
    try {
      final res = await _api.dio.get<dynamic>(ApiPaths.dashboardStats);
      return DashboardStats.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}

class DashboardStats {
  DashboardStats({
    required this.unbilledHours,
    required this.mtdInvoiced,
    required this.mtdPaid,
    required this.overdueInvoices,
    required this.maintenanceDue7d,
    required this.currency,
    required this.socialAccounts,
    required this.socialInboxUnread,
  });

  final double unbilledHours;
  final double mtdInvoiced;
  final double mtdPaid;
  final int overdueInvoices;
  final int maintenanceDue7d;
  final String currency;
  final List<SocialAccountSummary> socialAccounts;
  final int socialInboxUnread;

  factory DashboardStats.fromJson(Map<String, dynamic> json) => DashboardStats(
        unbilledHours: (json['unbilled_hours'] as num?)?.toDouble() ?? 0,
        mtdInvoiced:
            double.tryParse((json['mtd_invoiced'] ?? '0').toString()) ?? 0,
        mtdPaid: double.tryParse((json['mtd_paid'] ?? '0').toString()) ?? 0,
        overdueInvoices: (json['overdue_invoices'] as num?)?.toInt() ?? 0,
        maintenanceDue7d:
            (json['maintenance_due_7d'] as num?)?.toInt() ?? 0,
        currency: json['currency'] as String? ?? 'GBP',
        socialAccounts: ((json['social_accounts'] as List?) ?? [])
            .whereType<Map<String, dynamic>>()
            .map(SocialAccountSummary.fromJson)
            .toList(),
        socialInboxUnread: (json['social_inbox_unread'] as num?)?.toInt() ?? 0,
      );
}
