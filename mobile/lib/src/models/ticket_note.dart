class TicketNote {
  TicketNote({
    required this.id,
    required this.ticketId,
    required this.authorEmail,
    required this.body,
    required this.internal,
    required this.createdAt,
  });

  final int id;
  final int ticketId;
  final String authorEmail;
  final String body;
  final bool internal;
  final DateTime createdAt;

  factory TicketNote.fromJson(Map<String, dynamic> json) => TicketNote(
        id: json['id'] as int,
        ticketId: json['ticket'] as int? ?? 0,
        authorEmail: json['author_email'] as String? ?? '',
        body: json['body'] as String? ?? '',
        internal: json['internal'] as bool? ?? false,
        createdAt: DateTime.tryParse(json['created_at'] as String? ?? '') ??
            DateTime.now(),
      );
}
