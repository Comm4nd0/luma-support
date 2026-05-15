import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models/client.dart';
import '../models/invoice.dart';
import '../repositories/invoices_repository.dart';
import '../services/api_client.dart';
import '../theme.dart';
import 'widgets/client_picker.dart';
import 'widgets/invoice_line_editor.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../../src/widgets/luma_icon.dart';

class InvoiceCreateScreen extends StatefulWidget {
  const InvoiceCreateScreen({super.key});

  @override
  State<InvoiceCreateScreen> createState() => _InvoiceCreateScreenState();
}

class _InvoiceCreateScreenState extends State<InvoiceCreateScreen> {
  Client? _client;
  DateTime? _dueDate;
  final TextEditingController _notes = TextEditingController();
  final List<InvoiceLine> _lines = [];
  bool _saving = false;

  @override
  void dispose() {
    _notes.dispose();
    super.dispose();
  }

  Future<void> _pickClient() async {
    final api = context.read<ApiClient>();
    final picked = await showClientPicker(context, api);
    if (picked != null && mounted) {
      setState(() => _client = picked);
    }
  }

  Future<void> _pickDueDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _dueDate ?? now.add(const Duration(days: 14)),
      firstDate: now.subtract(const Duration(days: 365)),
      lastDate: now.add(const Duration(days: 365 * 5)),
    );
    if (picked != null && mounted) {
      setState(() => _dueDate = picked);
    }
  }

  Future<void> _addLine() async {
    final line = await showInvoiceLineEditor(context);
    if (line != null && mounted) {
      setState(() => _lines.add(line));
    }
  }

  Future<void> _editLine(int index) async {
    final updated = await showInvoiceLineEditor(
      context,
      initial: _lines[index],
    );
    if (updated != null && mounted) {
      setState(() => _lines[index] = updated);
    }
  }

  Future<void> _save() async {
    if (_client == null) {
      _snack('Pick a client first.');
      return;
    }
    if (_lines.isEmpty) {
      _snack('Add at least one line.');
      return;
    }
    setState(() => _saving = true);
    final messenger = ScaffoldMessenger.of(context);
    final router = GoRouter.of(context);
    try {
      final inv = await InvoicesRepository(context.read<ApiClient>()).create(
        clientId: _client!.id,
        lines: _lines.map((l) => l.toWritePayload(includeId: false)).toList(),
        dueDate: _dueDate,
        notes: _notes.text.trim().isEmpty ? null : _notes.text.trim(),
      );
      messenger.showSnackBar(
        SnackBar(content: Text('Created invoice #${inv.id}')),
      );
      router.go('/billing/invoices/${inv.id}');
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Create failed: $e')));
      setState(() => _saving = false);
    }
  }

  void _snack(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  double get _total => _lines.fold(0, (a, l) => a + l.lineTotal);

  @override
  Widget build(BuildContext context) {
    final money = NumberFormat.simpleCurrency(name: 'GBP');
    return Scaffold(
      appBar: AppBar(title: const Text('New invoice')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: ListTile(
              leading: const LumaIcon(PhosphorIconsDuotone.user),
              title: Text(_client?.name ?? 'Pick a client'),
              subtitle: _client == null
                  ? null
                  : Text(_client!.company.isEmpty
                      ? 'Client #${_client!.id}'
                      : _client!.company),
              trailing: const LumaIcon(PhosphorIconsDuotone.caretRight),
              onTap: _pickClient,
            ),
          ),
          const SizedBox(height: 8),
          Card(
            child: ListTile(
              leading: const LumaIcon(PhosphorIconsDuotone.calendar),
              title: Text(
                _dueDate == null
                    ? 'Due date (optional)'
                    : DateFormat.yMMMd().format(_dueDate!),
              ),
              trailing: _dueDate == null
                  ? const LumaIcon(PhosphorIconsDuotone.caretRight)
                  : IconButton(
                      icon: const LumaIcon(PhosphorIconsDuotone.x),
                      onPressed: () => setState(() => _dueDate = null),
                    ),
              onTap: _pickDueDate,
            ),
          ),
          const SizedBox(height: 16),
          const _SectionLabel('Lines'),
          const SizedBox(height: 8),
          if (_lines.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(16),
                child: Text('No lines yet.'),
              ),
            )
          else
            for (var i = 0; i < _lines.length; i++)
              Card(
                margin: const EdgeInsets.only(bottom: 8),
                child: ListTile(
                  title: Text(_lines[i].description.isEmpty
                      ? '(no description)'
                      : _lines[i].description),
                  subtitle: Text(
                    '${_qty(_lines[i].quantity)} × ${money.format(_lines[i].unitAmount)}',
                  ),
                  trailing: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(money.format(_lines[i].lineTotal)),
                      IconButton(
                        icon: const LumaIcon(PhosphorIconsDuotone.trash),
                        onPressed: () =>
                            setState(() => _lines.removeAt(i)),
                      ),
                    ],
                  ),
                  onTap: () => _editLine(i),
                ),
              ),
          OutlinedButton.icon(
            onPressed: _addLine,
            icon: const LumaIcon(PhosphorIconsDuotone.plus),
            label: const Text('Add line'),
          ),
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text('Total'),
                  Text(
                    money.format(_total),
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          const _SectionLabel('Notes (optional)'),
          const SizedBox(height: 8),
          TextField(
            controller: _notes,
            maxLines: 3,
            decoration: const InputDecoration(
              hintText: 'Anything the client needs to see…',
            ),
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: _saving ? null : _save,
            icon: _saving
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const LumaIcon(PhosphorIconsDuotone.check),
            label: Text(_saving ? 'Saving…' : 'Create draft invoice'),
          ),
        ],
      ),
    );
  }

  static String _qty(double q) {
    if (q == q.roundToDouble()) return q.toStringAsFixed(0);
    return q.toStringAsFixed(2);
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel(this.text);
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
