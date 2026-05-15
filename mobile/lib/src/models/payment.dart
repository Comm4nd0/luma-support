class Payment {
  Payment({
    required this.id,
    required this.invoiceId,
    required this.xeroPaymentId,
    required this.amount,
    required this.paidAt,
    required this.reference,
    required this.createdAt,
  });

  final int id;
  final int invoiceId;
  final String xeroPaymentId;
  final double amount;
  final DateTime? paidAt;
  final String reference;
  final DateTime createdAt;

  factory Payment.fromJson(Map<String, dynamic> json) => Payment(
        id: json['id'] as int,
        invoiceId: json['invoice'] as int? ?? 0,
        xeroPaymentId: json['xero_payment_id'] as String? ?? '',
        amount: _toDouble(json['amount']),
        paidAt: _parseDate(json['paid_at']),
        reference: json['reference'] as String? ?? '',
        createdAt: _parseDate(json['created_at']) ?? DateTime.now(),
      );
}

double _toDouble(dynamic v) {
  if (v == null) return 0;
  if (v is num) return v.toDouble();
  return double.tryParse(v.toString()) ?? 0;
}

DateTime? _parseDate(dynamic v) {
  if (v == null) return null;
  if (v is DateTime) return v;
  final s = v.toString();
  if (s.isEmpty) return null;
  return DateTime.tryParse(s);
}
