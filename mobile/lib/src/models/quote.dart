import 'quote_line.dart';

class Quote {
  Quote({
    required this.id,
    required this.number,
    required this.leadId,
    required this.clientId,
    required this.status,
    required this.statusDisplay,
    required this.validUntil,
    required this.subtotal,
    required this.tax,
    required this.total,
    required this.currency,
    required this.notes,
    required this.acceptToken,
    required this.sentAt,
    required this.acceptedAt,
    required this.acceptedByName,
    required this.rejectedAt,
    required this.rejectionReason,
    required this.convertedInvoiceId,
    required this.recipientName,
    required this.recipientEmail,
    required this.isExpired,
    required this.lines,
    required this.createdAt,
  });

  final int id;
  final String number;
  final int? leadId;
  final int? clientId;
  final String status;
  final String statusDisplay;
  final DateTime? validUntil;
  final String subtotal;
  final String tax;
  final String total;
  final String currency;
  final String notes;
  final String acceptToken;
  final DateTime? sentAt;
  final DateTime? acceptedAt;
  final String acceptedByName;
  final DateTime? rejectedAt;
  final String rejectionReason;
  final int? convertedInvoiceId;
  final String recipientName;
  final String recipientEmail;
  final bool isExpired;
  final List<QuoteLine> lines;
  final DateTime createdAt;

  factory Quote.fromJson(Map<String, dynamic> json) => Quote(
        id: json['id'] as int,
        number: (json['number'] as String?) ?? '',
        leadId: json['lead'] as int?,
        clientId: json['client'] as int?,
        status: (json['status'] as String?) ?? 'draft',
        statusDisplay: (json['status_display'] as String?) ?? '',
        validUntil: _parseDate(json['valid_until']),
        subtotal: json['subtotal']?.toString() ?? '0',
        tax: json['tax']?.toString() ?? '0',
        total: json['total']?.toString() ?? '0',
        currency: (json['currency'] as String?) ?? 'GBP',
        notes: (json['notes'] as String?) ?? '',
        acceptToken: (json['accept_token'] as String?) ?? '',
        sentAt: _parseDate(json['sent_at']),
        acceptedAt: _parseDate(json['accepted_at']),
        acceptedByName: (json['accepted_by_name'] as String?) ?? '',
        rejectedAt: _parseDate(json['rejected_at']),
        rejectionReason: (json['rejection_reason'] as String?) ?? '',
        convertedInvoiceId: json['converted_invoice'] as int?,
        recipientName: (json['recipient_name'] as String?) ?? '',
        recipientEmail: (json['recipient_email'] as String?) ?? '',
        isExpired: (json['is_expired'] as bool?) ?? false,
        lines: (json['lines'] as List? ?? const [])
            .map((j) => QuoteLine.fromJson(j as Map<String, dynamic>))
            .toList(),
        createdAt:
            DateTime.tryParse(json['created_at'] as String? ?? '') ??
                DateTime.now(),
      );

  static DateTime? _parseDate(dynamic value) {
    if (value is String && value.isNotEmpty) {
      return DateTime.tryParse(value);
    }
    return null;
  }
}
