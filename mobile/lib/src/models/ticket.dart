import 'ticket_tag.dart';

enum TicketPriority { critical, high, medium, low }

enum TicketStatus { newTicket, assigned, inProgress, waiting, resolved, closed }

TicketPriority priorityFromString(String? v) {
  switch (v) {
    case 'critical':
      return TicketPriority.critical;
    case 'high':
      return TicketPriority.high;
    case 'low':
      return TicketPriority.low;
    case 'medium':
    default:
      return TicketPriority.medium;
  }
}

String priorityToString(TicketPriority p) => p.name == 'newTicket' ? 'new' : p.name;

TicketStatus statusFromString(String? v) {
  switch (v) {
    case 'new':
      return TicketStatus.newTicket;
    case 'assigned':
      return TicketStatus.assigned;
    case 'in_progress':
      return TicketStatus.inProgress;
    case 'waiting':
      return TicketStatus.waiting;
    case 'resolved':
      return TicketStatus.resolved;
    case 'closed':
      return TicketStatus.closed;
    default:
      return TicketStatus.newTicket;
  }
}

String statusToWire(TicketStatus s) {
  switch (s) {
    case TicketStatus.newTicket:
      return 'new';
    case TicketStatus.assigned:
      return 'assigned';
    case TicketStatus.inProgress:
      return 'in_progress';
    case TicketStatus.waiting:
      return 'waiting';
    case TicketStatus.resolved:
      return 'resolved';
    case TicketStatus.closed:
      return 'closed';
  }
}

/// Human label for a status — matches the portal's Ticket.Status choices so
/// the Kanban lanes read the same on both front-ends.
String statusLabel(TicketStatus s) {
  switch (s) {
    case TicketStatus.newTicket:
      return 'New';
    case TicketStatus.assigned:
      return 'Assigned';
    case TicketStatus.inProgress:
      return 'In progress';
    case TicketStatus.waiting:
      return 'Waiting on client';
    case TicketStatus.resolved:
      return 'Resolved';
    case TicketStatus.closed:
      return 'Closed';
  }
}

class CsatResponse {
  CsatResponse({
    required this.id,
    required this.rating,
    required this.comment,
    required this.respondedAt,
  });

  final int id;
  final int? rating; // 1..5; null when the survey is pending
  final String comment;
  final DateTime? respondedAt;

  bool get hasRating => rating != null;

  factory CsatResponse.fromJson(Map<String, dynamic> json) => CsatResponse(
        id: json['id'] as int? ?? 0,
        rating: json['rating'] as int?,
        comment: json['comment'] as String? ?? '',
        respondedAt: _parseDate(json['responded_at']),
      );
}

class Ticket {
  Ticket({
    required this.id,
    required this.clientId,
    required this.clientName,
    required this.subject,
    required this.description,
    required this.priority,
    required this.status,
    required this.slaDeadline,
    required this.effectiveSlaDeadline,
    required this.slaPausedAt,
    required this.isBreached,
    required this.isPaused,
    required this.assignedToEmail,
    required this.csat,
    required this.tags,
    required this.createdAt,
  });

  final int id;
  final int clientId;
  final String clientName;
  final String subject;
  final String description;
  final TicketPriority priority;
  final TicketStatus status;
  final DateTime? slaDeadline;
  final DateTime? effectiveSlaDeadline;
  final DateTime? slaPausedAt;
  final bool isBreached;
  final bool isPaused;
  final String? assignedToEmail;
  final CsatResponse? csat;
  final List<TicketTag> tags;
  final DateTime createdAt;

  factory Ticket.fromJson(Map<String, dynamic> json) {
    final stored = _parseDate(json['sla_deadline']);
    final effective = _parseDate(json['effective_sla_deadline']) ?? stored;
    final tagJson = (json['tags'] as List?) ?? const [];
    return Ticket(
      id: json['id'] as int,
      clientId: json['client'] as int? ?? 0,
      clientName: json['client_name'] as String? ?? '',
      subject: json['subject'] as String? ?? '',
      description: json['description'] as String? ?? '',
      priority: priorityFromString(json['priority'] as String?),
      status: statusFromString(json['status'] as String?),
      slaDeadline: stored,
      effectiveSlaDeadline: effective,
      slaPausedAt: _parseDate(json['sla_paused_at']),
      isBreached: json['is_breached'] as bool? ?? false,
      isPaused: json['is_paused'] as bool? ?? (json['sla_paused_at'] != null),
      assignedToEmail: json['assigned_to_email'] as String?,
      csat: json['csat'] is Map
          ? CsatResponse.fromJson(json['csat'] as Map<String, dynamic>)
          : null,
      tags: tagJson
          .whereType<Map<String, dynamic>>()
          .map(TicketTag.fromJson)
          .toList(),
      createdAt: _parseDate(json['created_at']) ?? DateTime.now(),
    );
  }
}

DateTime? _parseDate(dynamic v) {
  if (v == null) return null;
  if (v is DateTime) return v;
  return DateTime.tryParse(v as String);
}
