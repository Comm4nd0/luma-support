DateTime? _parseDate(dynamic v) {
  if (v == null) return null;
  if (v is DateTime) return v;
  return DateTime.tryParse(v.toString());
}

double? _parseDouble(dynamic v) {
  if (v == null) return null;
  if (v is num) return v.toDouble();
  return double.tryParse(v.toString());
}

class SiteVisit {
  const SiteVisit({
    required this.id,
    required this.clientId,
    required this.userEmail,
    required this.startedAt,
    required this.endedAt,
    required this.latStart,
    required this.lonStart,
    required this.latEnd,
    required this.lonEnd,
    required this.notes,
    required this.durationMinutes,
    required this.timeEntryId,
  });

  final int id;
  final int clientId;
  final String? userEmail;
  final DateTime? startedAt;
  final DateTime? endedAt;
  final double? latStart;
  final double? lonStart;
  final double? latEnd;
  final double? lonEnd;
  final String notes;
  final int? durationMinutes;
  final int? timeEntryId;

  bool get isOpen => endedAt == null;

  factory SiteVisit.fromJson(Map<String, dynamic> json) => SiteVisit(
        id: json['id'] as int,
        clientId: json['client'] as int? ?? 0,
        userEmail: json['user_email'] as String?,
        startedAt: _parseDate(json['started_at']),
        endedAt: _parseDate(json['ended_at']),
        latStart: _parseDouble(json['lat_start']),
        lonStart: _parseDouble(json['lon_start']),
        latEnd: _parseDouble(json['lat_end']),
        lonEnd: _parseDouble(json['lon_end']),
        notes: json['notes'] as String? ?? '',
        durationMinutes: (json['duration_minutes'] as num?)?.toInt(),
        timeEntryId: (json['time_entry'] as num?)?.toInt(),
      );
}
