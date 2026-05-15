import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../models/invoice.dart';
import '../../theme.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../../../src/widgets/luma_icon.dart';

class InvoiceTile extends StatelessWidget {
  const InvoiceTile({super.key, required this.invoice, this.onTap});

  final Invoice invoice;
  final VoidCallback? onTap;

  Color _statusColor(InvoiceStatus s) {
    switch (s) {
      case InvoiceStatus.paid:
        return const Color(0xFF22C55E);
      case InvoiceStatus.authorised:
      case InvoiceStatus.sent:
        return const Color(0xFF38BDF8);
      case InvoiceStatus.draft:
        return kMuted;
      case InvoiceStatus.voided:
        return const Color(0xFFF43F5E);
      case InvoiceStatus.unknown:
        return kMuted;
    }
  }

  @override
  Widget build(BuildContext context) {
    final colour = _statusColor(invoice.status);
    final money = NumberFormat.simpleCurrency(name: invoice.currency);
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        onTap: onTap,
        title: Text(
          'Invoice #${invoice.id}',
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: Text(
          invoice.dueDate == null
              ? 'No due date'
              : 'Due ${DateFormat.yMMMd().format(invoice.dueDate!)}',
        ),
        leading: CircleAvatar(
          backgroundColor: colour.withOpacity(0.18),
          child: LumaIcon(PhosphorIconsDuotone.receipt, color: colour),
        ),
        trailing: Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              money.format(invoice.total),
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
            Text(invoice.status.name, style: const TextStyle(fontSize: 12)),
            if (invoice.isSyncedToXero)
              const Text(
                'Xero',
                style: TextStyle(color: Color(0xFF14B8A6), fontSize: 11),
              ),
          ],
        ),
      ),
    );
  }
}
