/// Named AppNotification to avoid clashing with material/scheduler's
/// `Notification` class.
class AppNotification {
  AppNotification({
    required this.id,
    required this.type,
    required this.title,
    required this.body,
    required this.relatedTicketId,
    required this.read,
    required this.createdAt,
  });

  final int id;
  final String type;
  final String title;
  final String body;
  final int? relatedTicketId;
  final bool read;
  final DateTime createdAt;

  factory AppNotification.fromJson(Map<String, dynamic> json) => AppNotification(
        id: json['id'] as int,
        type: json['type'] as String? ?? '',
        title: json['title'] as String? ?? '',
        body: json['body'] as String? ?? '',
        relatedTicketId: json['related_ticket'] as int?,
        read: json['read'] as bool? ?? false,
        createdAt: DateTime.tryParse(json['created_at'] as String? ?? '') ??
            DateTime.now(),
      );
}
