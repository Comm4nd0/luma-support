class LeadActivity {
  LeadActivity({
    required this.id,
    required this.leadId,
    required this.kind,
    required this.kindDisplay,
    required this.body,
    required this.actorEmail,
    required this.occurredAt,
  });

  final int id;
  final int leadId;
  final String kind;
  final String kindDisplay;
  final String body;
  final String actorEmail;
  final DateTime occurredAt;

  factory LeadActivity.fromJson(Map<String, dynamic> json) => LeadActivity(
        id: json['id'] as int,
        leadId: json['lead'] as int,
        kind: (json['kind'] as String?) ?? 'note',
        kindDisplay: (json['kind_display'] as String?) ?? '',
        body: (json['body'] as String?) ?? '',
        actorEmail: (json['actor_email'] as String?) ?? '',
        occurredAt:
            DateTime.tryParse(json['occurred_at'] as String? ?? '') ??
                DateTime.now(),
      );
}
