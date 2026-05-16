enum InvoiceStatus { draft, sent, authorised, paid, voided, unknown }

enum InvoiceKind { oneOff, contract, time, unknown }

InvoiceStatus invoiceStatusFromString(String? v) {
  switch (v) {
    case 'draft':
      return InvoiceStatus.draft;
    case 'sent':
      return InvoiceStatus.sent;
    case 'authorised':
      return InvoiceStatus.authorised;
    case 'paid':
      return InvoiceStatus.paid;
    case 'voided':
      return InvoiceStatus.voided;
    default:
      return InvoiceStatus.unknown;
  }
}

String invoiceStatusToWire(InvoiceStatus s) {
  switch (s) {
    case InvoiceStatus.draft:
      return 'draft';
    case InvoiceStatus.sent:
      return 'sent';
    case InvoiceStatus.authorised:
      return 'authorised';
    case InvoiceStatus.paid:
      return 'paid';
    case InvoiceStatus.voided:
      return 'voided';
    case InvoiceStatus.unknown:
      return '';
  }
}

InvoiceKind invoiceKindFromString(String? v) {
  switch (v) {
    case 'one_off':
      return InvoiceKind.oneOff;
    case 'contract':
      return InvoiceKind.contract;
    case 'time':
      return InvoiceKind.time;
    default:
      return InvoiceKind.unknown;
  }
}

class InvoiceLine {
  InvoiceLine({
    required this.id,
    required this.description,
    required this.quantity,
    required this.unitAmount,
    required this.lineTotal,
    required this.accountCode,
    required this.taxType,
    required this.timeEntryId,
  });

  final int id;
  final String description;
  final double quantity;
  final double unitAmount;
  final double lineTotal;
  final String accountCode;
  final String taxType;
  final int? timeEntryId;

  factory InvoiceLine.fromJson(Map<String, dynamic> json) => InvoiceLine(
        id: json['id'] as int? ?? 0,
        description: json['description'] as String? ?? '',
        quantity: _toDouble(json['quantity']),
        unitAmount: _toDouble(json['unit_amount']),
        lineTotal: _toDouble(json['line_total']),
        accountCode: json['account_code'] as String? ?? '',
        taxType: json['tax_type'] as String? ?? '',
        timeEntryId: json['time_entry'] as int?,
      );

  /// Payload for the nested `lines` array on POST/PATCH /invoices/. We only
  /// include `id` when this line already exists server-side so the backend
  /// diff can match-update; new lines omit it.
  Map<String, dynamic> toWritePayload({bool includeId = true}) => {
        if (includeId && id != 0) 'id': id,
        'description': description,
        'quantity': quantity.toStringAsFixed(2),
        'unit_amount': unitAmount.toStringAsFixed(2),
        if (accountCode.isNotEmpty) 'account_code': accountCode,
        if (taxType.isNotEmpty) 'tax_type': taxType,
      };
}

class Invoice {
  Invoice({
    required this.id,
    required this.clientId,
    required this.kind,
    required this.status,
    required this.periodStart,
    required this.periodEnd,
    required this.subtotal,
    required this.tax,
    required this.total,
    required this.currency,
    required this.dueDate,
    required this.notes,
    required this.xeroInvoiceId,
    required this.xeroStatus,
    required this.xeroSyncedAt,
    required this.stripePaymentLinkUrl,
    required this.sentAt,
    required this.paidAt,
    required this.lines,
    required this.createdAt,
    required this.updatedAt,
  });

  final int id;
  final int clientId;
  final InvoiceKind kind;
  final InvoiceStatus status;
  final DateTime? periodStart;
  final DateTime? periodEnd;
  final double subtotal;
  final double tax;
  final double total;
  final String currency;
  final DateTime? dueDate;
  final String notes;
  final String xeroInvoiceId;
  final String xeroStatus;
  final DateTime? xeroSyncedAt;
  final String stripePaymentLinkUrl;
  final DateTime? sentAt;
  final DateTime? paidAt;
  final List<InvoiceLine> lines;
  final DateTime createdAt;
  final DateTime? updatedAt;

  bool get isSyncedToXero => xeroInvoiceId.isNotEmpty;
  bool get hasStripeLink => stripePaymentLinkUrl.isNotEmpty;

  factory Invoice.fromJson(Map<String, dynamic> json) => Invoice(
        id: json['id'] as int,
        clientId: json['client'] as int? ?? 0,
        kind: invoiceKindFromString(json['kind'] as String?),
        status: invoiceStatusFromString(json['status'] as String?),
        periodStart: _parseDate(json['period_start']),
        periodEnd: _parseDate(json['period_end']),
        subtotal: _toDouble(json['subtotal']),
        tax: _toDouble(json['tax']),
        total: _toDouble(json['total']),
        currency: json['currency'] as String? ?? 'GBP',
        dueDate: _parseDate(json['due_date']),
        notes: json['notes'] as String? ?? '',
        xeroInvoiceId: json['xero_invoice_id'] as String? ?? '',
        xeroStatus: json['xero_status'] as String? ?? '',
        xeroSyncedAt: _parseDate(json['xero_synced_at']),
        stripePaymentLinkUrl:
            json['stripe_payment_link_url'] as String? ?? '',
        sentAt: _parseDate(json['sent_at']),
        paidAt: _parseDate(json['paid_at']),
        lines: ((json['lines'] as List?) ?? const [])
            .map((l) => InvoiceLine.fromJson(l as Map<String, dynamic>))
            .toList(),
        createdAt: _parseDate(json['created_at']) ?? DateTime.now(),
        updatedAt: _parseDate(json['updated_at']),
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
