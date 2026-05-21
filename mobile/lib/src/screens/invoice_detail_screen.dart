import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models/invoice.dart';
import '../repositories/invoices_repository.dart';
import '../services/api_client.dart';
import '../theme.dart';
import 'widgets/invoice_line_editor.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../../src/widgets/luma_icon.dart';

class InvoiceDetailScreen extends StatefulWidget {
  const InvoiceDetailScreen({super.key, required this.invoiceId});

  final int invoiceId;

  @override
  State<InvoiceDetailScreen> createState() => _InvoiceDetailScreenState();
}

class _InvoiceDetailScreenState extends State<InvoiceDetailScreen> {
  late Future<Invoice> _future;
  bool _busy = false;

  InvoicesRepository get _repo =>
      InvoicesRepository(context.read<ApiClient>());

  @override
  void initState() {
    super.initState();
    _future = _repo.get(widget.invoiceId);
  }

  void _refresh() {
    setState(() {
      _future = _repo.get(widget.invoiceId);
    });
  }

  Future<void> _withBusy(Future<void> Function() body) async {
    setState(() => _busy = true);
    try {
      await body();
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _snack(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  Future<void> _sendToXero() => _withBusy(() async {
        try {
          await _repo.sendToXero(widget.invoiceId);
          _snack('Queued for push to Xero.');
          _refresh();
        } catch (e) {
          _snack('Send failed: $e');
        }
      });

  Future<void> _setStatus(InvoiceStatus target, String label) async {
    final ok = await _confirm('Mark as $label?');
    if (!ok) return;
    await _withBusy(() async {
      try {
        await _repo.setStatus(widget.invoiceId, target);
        _snack('Status updated.');
        _refresh();
      } catch (e) {
        _snack('Status change failed: $e');
      }
    });
  }

  Future<void> _delete() async {
    final ok = await _confirm('Delete this draft invoice? This cannot be undone.');
    if (!ok) return;
    await _withBusy(() async {
      try {
        await _repo.delete(widget.invoiceId);
        if (mounted) {
          _snack('Invoice deleted.');
          context.pop();
        }
      } catch (e) {
        _snack('Delete failed: $e');
      }
    });
  }

  Future<bool> _confirm(String message) async {
    final res = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Confirm'),
          ),
        ],
      ),
    );
    return res ?? false;
  }

  Future<void> _editDueDate(Invoice inv) async {
    final picked = await showDatePicker(
      context: context,
      initialDate: inv.dueDate ?? DateTime.now().add(const Duration(days: 14)),
      firstDate: DateTime.now().subtract(const Duration(days: 365)),
      lastDate: DateTime.now().add(const Duration(days: 365 * 5)),
    );
    if (picked == null) return;
    await _patch({'dueDate': picked});
  }

  Future<void> _clearDueDate() => _patch({'clearDueDate': true});

  Future<void> _editNotes(Invoice inv) async {
    final controller = TextEditingController(text: inv.notes);
    final result = await showDialog<String?>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Notes'),
        content: TextField(
          controller: controller,
          maxLines: 5,
          autofocus: true,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, controller.text),
            child: const Text('Save'),
          ),
        ],
      ),
    );
    if (result == null) return;
    await _patch({'notes': result});
  }

  Future<void> _patch(Map<String, dynamic> updates) async {
    await _withBusy(() async {
      try {
        await _repo.update(
          widget.invoiceId,
          dueDate: updates['dueDate'] as DateTime?,
          clearDueDate: updates['clearDueDate'] == true,
          notes: updates['notes'] as String?,
          lines: updates['lines'] as List<Map<String, dynamic>>?,
        );
        _refresh();
      } catch (e) {
        _snack('Update failed: $e');
      }
    });
  }

  Future<void> _addLine(Invoice inv) async {
    final line = await showInvoiceLineEditor(context);
    if (line == null) return;
    final lines = [
      ...inv.lines.map((l) => l.toWritePayload()),
      line.toWritePayload(includeId: false),
    ];
    await _patch({'lines': lines});
  }

  Future<void> _editLine(Invoice inv, int index) async {
    final updated = await showInvoiceLineEditor(
      context,
      initial: inv.lines[index],
    );
    if (updated == null) return;
    final lines = inv.lines
        .asMap()
        .entries
        .map((e) => e.key == index
            ? updated.toWritePayload(includeId: true)
            : e.value.toWritePayload())
        .toList();
    await _patch({'lines': lines});
  }

  Future<void> _deleteLine(Invoice inv, int index) async {
    final ok = await _confirm('Delete this line?');
    if (!ok) return;
    final lines = inv.lines
        .asMap()
        .entries
        .where((e) => e.key != index)
        .map((e) => e.value.toWritePayload())
        .toList();
    await _patch({'lines': lines});
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: FutureBuilder<Invoice>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Scaffold(
              body: Center(child: CircularProgressIndicator()),
            );
          }
          if (snap.hasError) {
            return Scaffold(
              appBar: AppBar(),
              body: Center(child: Text('Error: ${snap.error}')),
            );
          }
          final inv = snap.data!;
          final money = NumberFormat.simpleCurrency(name: inv.currency);
          final isDraft = inv.status == InvoiceStatus.draft;
          return Scaffold(
            appBar: AppBar(
              title: Text('Invoice #${widget.invoiceId}'),
              actions: [
                if (isDraft)
                  IconButton(
                    icon: const LumaIcon(PhosphorIconsDuotone.trash),
                    tooltip: 'Delete draft',
                    onPressed: _busy ? null : _delete,
                  ),
              ],
            ),
            body: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                _HeaderCard(invoice: inv, money: money),
                const SizedBox(height: 16),
                _StatusActions(
                  invoice: inv,
                  busy: _busy,
                  onSendToXero: _sendToXero,
                  onMarkSent: () =>
                      _setStatus(InvoiceStatus.sent, 'sent'),
                  onMarkVoided: () =>
                      _setStatus(InvoiceStatus.voided, 'voided'),
                ),
                const SizedBox(height: 16),
                const _Section('Details'),
                const SizedBox(height: 8),
                Card(
                  child: Column(
                    children: [
                      ListTile(
                        leading: const LumaIcon(PhosphorIconsDuotone.calendar),
                        title: const Text('Due date'),
                        subtitle: Text(
                          inv.dueDate == null
                              ? '—'
                              : DateFormat.yMMMd().format(inv.dueDate!),
                        ),
                        trailing: !isDraft
                            ? null
                            : Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  if (inv.dueDate != null)
                                    IconButton(
                                      icon: const LumaIcon(PhosphorIconsDuotone.x),
                                      onPressed: _busy ? null : _clearDueDate,
                                    ),
                                  const LumaIcon(PhosphorIconsDuotone.caretRight),
                                ],
                              ),
                        onTap:
                            !isDraft ? null : () => _editDueDate(inv),
                      ),
                      const Divider(height: 1),
                      ListTile(
                        leading: const LumaIcon(PhosphorIconsDuotone.note),
                        title: const Text('Notes'),
                        subtitle: Text(
                          inv.notes.isEmpty ? 'None' : inv.notes,
                          maxLines: 4,
                          overflow: TextOverflow.ellipsis,
                        ),
                        trailing: isDraft
                            ? const LumaIcon(PhosphorIconsDuotone.caretRight)
                            : null,
                        onTap: !isDraft ? null : () => _editNotes(inv),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                Row(
                  children: [
                    const Expanded(child: _Section('Lines')),
                    if (isDraft)
                      TextButton.icon(
                        onPressed: _busy ? null : () => _addLine(inv),
                        icon: const LumaIcon(PhosphorIconsDuotone.plus),
                        label: const Text('Add line'),
                      ),
                  ],
                ),
                const SizedBox(height: 8),
                if (inv.lines.isEmpty)
                  const Card(
                    child: Padding(
                      padding: EdgeInsets.all(16),
                      child: Text('No line items.'),
                    ),
                  )
                else
                  for (var i = 0; i < inv.lines.length; i++)
                    Card(
                      margin: const EdgeInsets.only(bottom: 8),
                      child: ListTile(
                        title: Text(inv.lines[i].description.isEmpty
                            ? '(no description)'
                            : inv.lines[i].description),
                        subtitle: Text(
                          '${_qty(inv.lines[i].quantity)} × ${money.format(inv.lines[i].unitAmount)}'
                          '${inv.lines[i].taxType.isEmpty ? '' : ' · ${inv.lines[i].taxType}'}',
                        ),
                        trailing: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Text(
                              money.format(inv.lines[i].lineTotal),
                              style: const TextStyle(
                                  fontWeight: FontWeight.w600),
                            ),
                            if (isDraft)
                              IconButton(
                                icon: const LumaIcon(PhosphorIconsDuotone.trash),
                                onPressed: _busy
                                    ? null
                                    : () => _deleteLine(inv, i),
                              ),
                          ],
                        ),
                        onTap: !isDraft
                            ? null
                            : () => _editLine(inv, i),
                      ),
                    ),
                const SizedBox(height: 16),
                _TotalsCard(invoice: inv, money: money),
                if (inv.dunningEvents.isNotEmpty) ...[
                  const SizedBox(height: 16),
                  const _Section('Dunning timeline'),
                  const SizedBox(height: 8),
                  for (final ev in inv.dunningEvents)
                    Card(
                      margin: const EdgeInsets.only(bottom: 6),
                      child: ListTile(
                        dense: true,
                        leading: Icon(
                          ev.emailed ? Icons.mail_outline : Icons.notifications_none,
                          size: 18,
                        ),
                        title: Text('${ev.bucket}d reminder — ${ev.daysOverdue}d overdue'),
                        subtitle: Text(ev.sentAt?.toString() ?? ''),
                      ),
                    ),
                ],
              ],
            ),
          );
        },
      ),
    );
  }

  static String _qty(double q) {
    if (q == q.roundToDouble()) return q.toStringAsFixed(0);
    return q.toStringAsFixed(2);
  }
}

class _HeaderCard extends StatelessWidget {
  const _HeaderCard({required this.invoice, required this.money});

  final Invoice invoice;
  final NumberFormat money;

  @override
  Widget build(BuildContext context) {
    final due = invoice.dueDate;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  money.format(invoice.total),
                  style: const TextStyle(
                    fontSize: 26,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                Chip(label: Text(invoice.status.name)),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              due == null
                  ? 'No due date'
                  : 'Due ${DateFormat.yMMMd().format(due)}',
              style: const TextStyle(color: kMuted),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                LumaIcon(
                  invoice.isSyncedToXero ? PhosphorIconsDuotone.checkCircle : PhosphorIconsDuotone.arrowsClockwise,
                  size: 16,
                  color: invoice.isSyncedToXero ? kPrimary : kMuted,
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    invoice.isSyncedToXero
                        ? 'Xero ${invoice.xeroStatus.isEmpty ? 'synced' : invoice.xeroStatus}'
                            '${invoice.xeroSyncedAt == null ? '' : ' · ${DateFormat.yMMMd().add_jm().format(invoice.xeroSyncedAt!.toLocal())}'}'
                        : 'Not synced to Xero',
                    style: const TextStyle(color: kMuted),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _StatusActions extends StatelessWidget {
  const _StatusActions({
    required this.invoice,
    required this.busy,
    required this.onSendToXero,
    required this.onMarkSent,
    required this.onMarkVoided,
  });

  final Invoice invoice;
  final bool busy;
  final VoidCallback onSendToXero;
  final VoidCallback onMarkSent;
  final VoidCallback onMarkVoided;

  Future<void> _openPaymentLink(BuildContext context) async {
    final uri = Uri.tryParse(invoice.stripePaymentLinkUrl);
    if (uri == null) return;
    final ok = await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!ok && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not open the payment link.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final canMarkSent = invoice.status == InvoiceStatus.draft;
    final canVoid = invoice.status == InvoiceStatus.draft ||
        invoice.status == InvoiceStatus.sent;
    final canSendToXero = !invoice.isSyncedToXero;
    final canPay = invoice.hasStripeLink;
    if (!canMarkSent && !canVoid && !canSendToXero && !canPay) {
      return const SizedBox.shrink();
    }
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        if (canPay)
          ElevatedButton.icon(
            onPressed: busy ? null : () => _openPaymentLink(context),
            icon: const Icon(Icons.open_in_new),
            label: const Text('Pay online'),
          ),
        if (canSendToXero)
          ElevatedButton.icon(
            onPressed: busy ? null : onSendToXero,
            icon: const LumaIcon(PhosphorIconsDuotone.cloudArrowUp),
            label: const Text('Send to Xero'),
          ),
        if (canMarkSent)
          OutlinedButton.icon(
            onPressed: busy ? null : onMarkSent,
            icon: const LumaIcon(PhosphorIconsDuotone.envelopeOpen),
            label: const Text('Mark sent'),
          ),
        if (canVoid)
          OutlinedButton.icon(
            onPressed: busy ? null : onMarkVoided,
            icon: const LumaIcon(PhosphorIconsDuotone.prohibit),
            label: const Text('Void'),
          ),
      ],
    );
  }
}

class _TotalsCard extends StatelessWidget {
  const _TotalsCard({required this.invoice, required this.money});

  final Invoice invoice;
  final NumberFormat money;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            _row('Subtotal', money.format(invoice.subtotal)),
            const SizedBox(height: 4),
            _row('Tax', money.format(invoice.tax)),
            const Divider(height: 16),
            _row('Total', money.format(invoice.total), bold: true),
          ],
        ),
      ),
    );
  }

  Widget _row(String label, String value, {bool bold = false}) {
    final style = bold
        ? const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)
        : const TextStyle();
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [Text(label, style: style), Text(value, style: style)],
    );
  }
}

class _Section extends StatelessWidget {
  const _Section(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => Text(
        text,
        style: const TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w600,
          color: kMuted,
        ),
      );
}
