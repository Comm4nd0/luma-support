enum MaintenanceCadence {
  weekly,
  monthly,
  quarterly,
  biannual,
  annual,
  unknown,
}

MaintenanceCadence cadenceFromString(String? v) {
  switch (v) {
    case 'weekly':
      return MaintenanceCadence.weekly;
    case 'monthly':
      return MaintenanceCadence.monthly;
    case 'quarterly':
      return MaintenanceCadence.quarterly;
    case 'biannual':
      return MaintenanceCadence.biannual;
    case 'annual':
      return MaintenanceCadence.annual;
    default:
      return MaintenanceCadence.unknown;
  }
}

String cadenceLabel(MaintenanceCadence c) {
  switch (c) {
    case MaintenanceCadence.weekly:
      return 'Weekly';
    case MaintenanceCadence.monthly:
      return 'Monthly';
    case MaintenanceCadence.quarterly:
      return 'Quarterly';
    case MaintenanceCadence.biannual:
      return 'Every 6 months';
    case MaintenanceCadence.annual:
      return 'Annual';
    case MaintenanceCadence.unknown:
      return 'Unknown';
  }
}

class MaintenanceSchedule {
  MaintenanceSchedule({
    required this.id,
    required this.clientId,
    required this.clientName,
    required this.systemId,
    required this.systemName,
    required this.cadence,
    required this.nextRunAt,
    required this.templateSubject,
    required this.templateDescription,
    required this.priority,
    required this.defaultAssigneeId,
    required this.active,
    required this.lastRunAt,
  });

  final int id;
  final int clientId;
  final String clientName;
  final int? systemId;
  final String? systemName;
  final MaintenanceCadence cadence;
  final DateTime? nextRunAt;
  final String templateSubject;
  final String templateDescription;
  final String priority;
  final int? defaultAssigneeId;
  final bool active;
  final DateTime? lastRunAt;

  factory MaintenanceSchedule.fromJson(Map<String, dynamic> json) =>
      MaintenanceSchedule(
        id: json['id'] as int,
        clientId: json['client'] as int? ?? 0,
        clientName: json['client_name'] as String? ?? '',
        systemId: json['system'] as int?,
        systemName: json['system_name'] as String?,
        cadence: cadenceFromString(json['cadence'] as String?),
        nextRunAt: _parseDate(json['next_run_at']),
        templateSubject: json['template_subject'] as String? ?? '',
        templateDescription: json['template_description'] as String? ?? '',
        priority: json['priority'] as String? ?? '',
        defaultAssigneeId: json['default_assignee'] as int?,
        active: json['active'] as bool? ?? true,
        lastRunAt: _parseDate(json['last_run_at']),
      );
}

DateTime? _parseDate(dynamic v) {
  if (v == null) return null;
  if (v is DateTime) return v;
  final s = v.toString();
  if (s.isEmpty) return null;
  return DateTime.tryParse(s);
}
