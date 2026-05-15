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
    required this.isBreached,
    required this.assignedToEmail,
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
  final bool isBreached;
  final String? assignedToEmail;
  final DateTime createdAt;

  factory Ticket.fromJson(Map<String, dynamic> json) => Ticket(
        id: json['id'] as int,
        clientId: json['client'] as int? ?? 0,
        clientName: json['client_name'] as String? ?? '',
        subject: json['subject'] as String? ?? '',
        description: json['description'] as String? ?? '',
        priority: priorityFromString(json['priority'] as String?),
        status: statusFromString(json['status'] as String?),
        slaDeadline: _parseDate(json['sla_deadline']),
        isBreached: json['is_breached'] as bool? ?? false,
        assignedToEmail: json['assigned_to_email'] as String?,
        createdAt: _parseDate(json['created_at']) ?? DateTime.now(),
      );
}

DateTime? _parseDate(dynamic v) {
  if (v == null) return null;
  if (v is DateTime) return v;
  return DateTime.tryParse(v as String);
}
