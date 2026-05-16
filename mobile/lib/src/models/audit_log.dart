class AuditLogEntry {
  AuditLogEntry({
    required this.id,
    required this.actorEmail,
    required this.action,
    required this.targetModel,
    required this.targetRepr,
    required this.ip,
    required this.metadata,
    required this.createdAt,
  });

  final int id;
  final String? actorEmail;
  final String action;
  final String? targetModel;
  final String targetRepr;
  final String? ip;
  final Map<String, dynamic> metadata;
  final DateTime createdAt;

  factory AuditLogEntry.fromJson(Map<String, dynamic> json) => AuditLogEntry(
        id: json['id'] as int,
        actorEmail: json['actor_email'] as String?,
        action: json['action'] as String? ?? '',
        targetModel: json['target_model'] as String?,
        targetRepr: json['target_repr'] as String? ?? '',
        ip: json['ip'] as String?,
        metadata: (json['metadata'] as Map?)?.cast<String, dynamic>() ?? {},
        createdAt:
            DateTime.tryParse(json['created_at'] as String? ?? '') ??
                DateTime.now(),
      );
}
