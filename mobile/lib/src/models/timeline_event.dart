/// Mirrors the `TimelineEvent` dataclass in clients/timeline.py, served by
/// the client `timeline` API action.
class TimelineEvent {
  const TimelineEvent({
    required this.kind,
    required this.occurredAt,
    required this.title,
    required this.body,
    required this.url,
    required this.pill,
  });

  /// "ticket" | "ticket_note" | "quote" | "invoice" | "lead_activity"
  final String kind;
  final DateTime? occurredAt;
  final String title;
  final String body;
  final String url; // in-app link, e.g. /tickets/42/
  final String pill; // visual chip, e.g. "open", "paid"

  factory TimelineEvent.fromJson(Map<String, dynamic> json) => TimelineEvent(
        kind: json['kind'] as String? ?? '',
        occurredAt: json['occurred_at'] == null
            ? null
            : DateTime.tryParse(json['occurred_at'].toString()),
        title: json['title'] as String? ?? '',
        body: json['body'] as String? ?? '',
        url: json['url'] as String? ?? '',
        pill: json['pill'] as String? ?? '',
      );
}
