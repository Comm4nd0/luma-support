import 'package:flutter/material.dart';

import '../../models/invoice.dart';

/// Modal sheet that edits a single [InvoiceLine] (or creates a new one when
/// [initial] is null). Returns the new/updated line, or null if cancelled.
Future<InvoiceLine?> showInvoiceLineEditor(
  BuildContext context, {
  InvoiceLine? initial,
}) {
  return showModalBottomSheet<InvoiceLine>(
    context: context,
    isScrollControlled: true,
    builder: (ctx) => Padding(
      padding: EdgeInsets.only(
        bottom: MediaQuery.of(ctx).viewInsets.bottom,
      ),
      child: _InvoiceLineEditor(initial: initial),
    ),
  );
}

class _InvoiceLineEditor extends StatefulWidget {
  const _InvoiceLineEditor({this.initial});
  final InvoiceLine? initial;

  @override
  State<_InvoiceLineEditor> createState() => _InvoiceLineEditorState();
}

class _InvoiceLineEditorState extends State<_InvoiceLineEditor> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _description;
  late final TextEditingController _quantity;
  late final TextEditingController _unitAmount;
  late final TextEditingController _accountCode;
  late final TextEditingController _taxType;

  @override
  void initState() {
    super.initState();
    final i = widget.initial;
    _description = TextEditingController(text: i?.description ?? '');
    _quantity = TextEditingController(
      text: i == null ? '1' : _trim(i.quantity),
    );
    _unitAmount = TextEditingController(
      text: i == null ? '' : _trim(i.unitAmount),
    );
    _accountCode = TextEditingController(text: i?.accountCode ?? '');
    _taxType = TextEditingController(text: i?.taxType ?? '');
  }

  @override
  void dispose() {
    _description.dispose();
    _quantity.dispose();
    _unitAmount.dispose();
    _accountCode.dispose();
    _taxType.dispose();
    super.dispose();
  }

  static String _trim(double v) {
    if (v == v.roundToDouble()) return v.toStringAsFixed(0);
    return v.toStringAsFixed(2);
  }

  void _submit() {
    if (!_formKey.currentState!.validate()) return;
    final qty = double.parse(_quantity.text.trim());
    final unit = double.parse(_unitAmount.text.trim());
    final line = InvoiceLine(
      id: widget.initial?.id ?? 0,
      description: _description.text.trim(),
      quantity: qty,
      unitAmount: unit,
      lineTotal: qty * unit,
      accountCode: _accountCode.text.trim(),
      taxType: _taxType.text.trim(),
      timeEntryId: widget.initial?.timeEntryId,
    );
    Navigator.of(context).pop(line);
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Form(
        key: _formKey,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              widget.initial == null ? 'New line' : 'Edit line',
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _description,
              decoration: const InputDecoration(labelText: 'Description'),
              maxLength: 500,
              validator: (v) =>
                  (v == null || v.trim().isEmpty) ? 'Required' : null,
            ),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    controller: _quantity,
                    decoration: const InputDecoration(labelText: 'Quantity'),
                    keyboardType: const TextInputType.numberWithOptions(
                      decimal: true,
                    ),
                    validator: _validateDecimal,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextFormField(
                    controller: _unitAmount,
                    decoration: const InputDecoration(labelText: 'Unit amount'),
                    keyboardType: const TextInputType.numberWithOptions(
                      decimal: true,
                    ),
                    validator: _validateDecimal,
                  ),
                ),
              ],
            ),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    controller: _accountCode,
                    decoration: const InputDecoration(
                      labelText: 'Account code (optional)',
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextFormField(
                    controller: _taxType,
                    decoration: const InputDecoration(
                      labelText: 'Tax type (optional)',
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () => Navigator.of(context).pop(),
                    child: const Text('Cancel'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: ElevatedButton(
                    onPressed: _submit,
                    child: const Text('Save'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }

  String? _validateDecimal(String? v) {
    if (v == null || v.trim().isEmpty) return 'Required';
    final n = double.tryParse(v.trim());
    if (n == null) return 'Not a number';
    if (n < 0) return 'Must be ≥ 0';
    return null;
  }
}
