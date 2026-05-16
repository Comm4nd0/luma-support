import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/contact.dart';
import '../repositories/contacts_repository.dart';
import '../services/api_client.dart';

/// Staff-only form for creating/editing a Contact under a Client.
/// Parity with the portal's /clients/<id>/contacts/new/ and
/// /contacts/<id>/edit/ pages.
class ContactFormScreen extends StatefulWidget {
  const ContactFormScreen({
    super.key,
    required this.clientId,
    this.contact,
  });

  final int clientId;
  final Contact? contact;

  bool get isEdit => contact != null;

  @override
  State<ContactFormScreen> createState() => _ContactFormScreenState();
}

class _ContactFormScreenState extends State<ContactFormScreen> {
  final _form = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _phone = TextEditingController();
  final _title = TextEditingController();
  bool _isPrimary = false;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    final c = widget.contact;
    if (c != null) {
      _name.text = c.name;
      _email.text = c.email;
      _phone.text = c.phone;
      _title.text = c.title;
      _isPrimary = c.isPrimary;
    }
  }

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _phone.dispose();
    _title.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _saving = true);
    final messenger = ScaffoldMessenger.of(context);
    final repo = ContactsRepository(context.read<ApiClient>());
    try {
      if (widget.isEdit) {
        await repo.update(
          widget.contact!.id,
          clientId: widget.clientId,
          name: _name.text.trim(),
          email: _email.text.trim(),
          phone: _phone.text.trim(),
          title: _title.text.trim(),
          isPrimary: _isPrimary,
        );
      } else {
        await repo.create(
          clientId: widget.clientId,
          name: _name.text.trim(),
          email: _email.text.trim(),
          phone: _phone.text.trim(),
          title: _title.text.trim(),
          isPrimary: _isPrimary,
        );
      }
      if (!mounted) return;
      messenger.showSnackBar(
        SnackBar(
          content: Text(widget.isEdit ? 'Contact updated.' : 'Contact added.'),
        ),
      );
      Navigator.of(context).pop(true);
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Save failed: $e')));
      setState(() => _saving = false);
    }
  }

  Future<void> _delete() async {
    if (widget.contact!.isPrimary) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Cannot delete the primary contact. Promote another contact first.',
          ),
        ),
      );
      return;
    }
    final confirm = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Delete contact?'),
        content: Text('Remove ${widget.contact!.name} from this client?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirm != true) return;
    final messenger = ScaffoldMessenger.of(context);
    try {
      await ContactsRepository(context.read<ApiClient>())
          .delete(widget.contact!.id);
      if (!mounted) return;
      messenger.showSnackBar(const SnackBar(content: Text('Contact removed.')));
      Navigator.of(context).pop(true);
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Delete failed: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.isEdit ? 'Edit contact' : 'New contact'),
        actions: [
          if (widget.isEdit)
            IconButton(
              tooltip: 'Delete',
              icon: const Icon(Icons.delete_outline),
              onPressed: _delete,
            ),
        ],
      ),
      body: Form(
        key: _form,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            TextFormField(
              controller: _name,
              decoration: const InputDecoration(labelText: 'Name'),
              validator: (v) =>
                  v == null || v.trim().isEmpty ? 'Required' : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _title,
              decoration:
                  const InputDecoration(labelText: 'Title (e.g. IT Manager)'),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _email,
              keyboardType: TextInputType.emailAddress,
              decoration: const InputDecoration(labelText: 'Email'),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _phone,
              keyboardType: TextInputType.phone,
              decoration: const InputDecoration(labelText: 'Phone'),
            ),
            const SizedBox(height: 12),
            SwitchListTile(
              value: _isPrimary,
              onChanged: (v) => setState(() => _isPrimary = v),
              title: const Text('Primary contact'),
              subtitle: const Text(
                'The primary contact mirrors the client name/email/phone.',
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
                  : const Icon(Icons.check),
              label: Text(widget.isEdit ? 'Save changes' : 'Add contact'),
            ),
          ],
        ),
      ),
    );
  }
}
