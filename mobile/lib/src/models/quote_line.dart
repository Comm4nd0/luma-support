class QuoteLine {
  QuoteLine({
    required this.id,
    required this.description,
    required this.quantity,
    required this.unitAmount,
    required this.lineTotal,
  });

  final int id;
  final String description;
  final String quantity;
  final String unitAmount;
  final String lineTotal;

  factory QuoteLine.fromJson(Map<String, dynamic> json) => QuoteLine(
        id: json['id'] as int? ?? 0,
        description: (json['description'] as String?) ?? '',
        quantity: json['quantity']?.toString() ?? '0',
        unitAmount: json['unit_amount']?.toString() ?? '0',
        lineTotal: json['line_total']?.toString() ?? '0',
      );

  Map<String, dynamic> toJson() => {
        'description': description,
        'quantity': quantity,
        'unit_amount': unitAmount,
      };
}
