class TimeEntry {
  TimeEntry({
    required this.id,
    required this.ticketId,
    required this.userEmail,
    required this.minutes,
    required this.description,
    required this.billable,
    required this.createdAt,
  });

  final int id;
  final int ticketId;
  final String userEmail;
  final int minutes;
  final String description;
  final bool billable;
  final DateTime createdAt;

  factory TimeEntry.fromJson(Map<String, dynamic> json) => TimeEntry(
        id: json['id'] as int,
        ticketId: json['ticket'] as int? ?? 0,
        userEmail: json['user_email'] as String? ?? '',
        minutes: json['minutes'] as int? ?? 0,
        description: json['description'] as String? ?? '',
        billable: json['billable'] as bool? ?? true,
        createdAt: DateTime.tryParse(json['created_at'] as String? ?? '') ??
            DateTime.now(),
      );
}
