enum SystemHealth { unknown, ok, degraded, down }

SystemHealth healthFromString(String? v) {
  switch (v) {
    case 'ok':
      return SystemHealth.ok;
    case 'degraded':
      return SystemHealth.degraded;
    case 'down':
      return SystemHealth.down;
    default:
      return SystemHealth.unknown;
  }
}

String healthLabel(SystemHealth h) {
  switch (h) {
    case SystemHealth.ok:
      return 'OK';
    case SystemHealth.degraded:
      return 'Degraded';
    case SystemHealth.down:
      return 'Down';
    case SystemHealth.unknown:
      return 'Unknown';
  }
}

class ClientSystem {
  ClientSystem({
    required this.id,
    required this.clientId,
    required this.type,
    required this.name,
    required this.description,
    required this.monitoringUrl,
    required this.health,
    required this.lastCheckedAt,
    required this.devicesOnline,
    required this.devicesOffline,
  });

  final int id;
  final int clientId;
  final String type;
  final String name;
  final String description;
  final String monitoringUrl;
  final SystemHealth health;
  final DateTime? lastCheckedAt;
  final int? devicesOnline;
  final int? devicesOffline;

  factory ClientSystem.fromJson(Map<String, dynamic> json) {
    final devices = json['devices_json'];
    int? online;
    int? offline;
    if (devices is Map) {
      online = (devices['online'] as num?)?.toInt();
      offline = (devices['offline'] as num?)?.toInt();
    }
    return ClientSystem(
      id: json['id'] as int,
      clientId: json['client'] as int? ?? 0,
      type: json['type'] as String? ?? '',
      name: json['name'] as String? ?? '',
      description: json['description'] as String? ?? '',
      monitoringUrl: json['monitoring_url'] as String? ?? '',
      health: healthFromString(json['health_status'] as String?),
      lastCheckedAt: _parseDate(json['last_checked_at']),
      devicesOnline: online,
      devicesOffline: offline,
    );
  }
}

DateTime? _parseDate(dynamic v) {
  if (v == null) return null;
  if (v is DateTime) return v;
  final s = v.toString();
  if (s.isEmpty) return null;
  return DateTime.tryParse(s);
}
