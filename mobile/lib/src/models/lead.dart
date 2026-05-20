import 'lead_activity.dart';

class Lead {
  Lead({
    required this.id,
    required this.name,
    required this.email,
    required this.phone,
    required this.company,
    required this.customerType,
    required this.source,
    required this.sourceDisplay,
    required this.sourceDetail,
    required this.referringClientId,
    required this.referringClientName,
    required this.interest,
    required this.estimatedValue,
    required this.stage,
    required this.stageDisplay,
    required this.nextActionAt,
    required this.assignedToId,
    required this.assignedToEmail,
    required this.convertedClientId,
    required this.convertedClientName,
    required this.convertedAt,
    required this.lostReason,
    required this.isOverdue,
    required this.activities,
    required this.createdAt,
    required this.updatedAt,
  });

  final int id;
  final String name;
  final String email;
  final String phone;
  final String company;
  final String customerType;
  final String source;
  final String sourceDisplay;
  final String sourceDetail;
  final int? referringClientId;
  final String referringClientName;
  final String interest;
  final String? estimatedValue;
  final String stage;
  final String stageDisplay;
  final DateTime? nextActionAt;
  final int? assignedToId;
  final String assignedToEmail;
  final int? convertedClientId;
  final String convertedClientName;
  final DateTime? convertedAt;
  final String lostReason;
  final bool isOverdue;
  final List<LeadActivity> activities;
  final DateTime createdAt;
  final DateTime? updatedAt;

  bool get isActive => const {
        'new',
        'contacted',
        'qualified',
        'quoted',
      }.contains(stage);

  factory Lead.fromJson(Map<String, dynamic> json) => Lead(
        id: json['id'] as int,
        name: (json['name'] as String?) ?? '',
        email: (json['email'] as String?) ?? '',
        phone: (json['phone'] as String?) ?? '',
        company: (json['company'] as String?) ?? '',
        customerType: (json['customer_type'] as String?) ?? 'home',
        source: (json['source'] as String?) ?? 'other',
        sourceDisplay: (json['source_display'] as String?) ?? '',
        sourceDetail: (json['source_detail'] as String?) ?? '',
        referringClientId: json['referring_client'] as int?,
        referringClientName:
            (json['referring_client_name'] as String?) ?? '',
        interest: (json['interest'] as String?) ?? '',
        estimatedValue: json['estimated_value']?.toString(),
        stage: (json['stage'] as String?) ?? 'new',
        stageDisplay: (json['stage_display'] as String?) ?? '',
        nextActionAt: _parseDate(json['next_action_at']),
        assignedToId: json['assigned_to'] as int?,
        assignedToEmail: (json['assigned_to_email'] as String?) ?? '',
        convertedClientId: json['converted_client'] as int?,
        convertedClientName:
            (json['converted_client_name'] as String?) ?? '',
        convertedAt: _parseDate(json['converted_at']),
        lostReason: (json['lost_reason'] as String?) ?? '',
        isOverdue: (json['is_overdue'] as bool?) ?? false,
        activities: (json['activities'] as List? ?? const [])
            .map((j) => LeadActivity.fromJson(j as Map<String, dynamic>))
            .toList(),
        createdAt:
            DateTime.tryParse(json['created_at'] as String? ?? '') ??
                DateTime.now(),
        updatedAt: _parseDate(json['updated_at']),
      );

  static DateTime? _parseDate(dynamic value) {
    if (value is String && value.isNotEmpty) {
      return DateTime.tryParse(value);
    }
    return null;
  }
}
