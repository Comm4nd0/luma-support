import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../models/client.dart';
import '../repositories/clients_repository.dart';
import '../services/api_client.dart';

/// Loads a client by id before rendering the edit form. Used when the edit
/// route is hit directly (e.g. from the client-detail "edit" icon) without
/// the Client object being passed via GoRouter's `extra`.
class ClientEditLoader extends StatefulWidget {
  const ClientEditLoader({super.key, required this.clientId});

  final int clientId;

  @override
  State<ClientEditLoader> createState() => _ClientEditLoaderState();
}

class _ClientEditLoaderState extends State<ClientEditLoader> {
  late Future<Client> _future;

  @override
  void initState() {
    super.initState();
    _future =
        ClientsRepository(context.read<ApiClient>()).get(widget.clientId);
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Client>(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }
        if (snap.hasError || snap.data == null) {
          return Scaffold(
            appBar: AppBar(title: const Text('Edit client')),
            body: Center(child: Text('Error: ${snap.error}')),
          );
        }
        return ClientFormScreen(client: snap.data!);
      },
    );
  }
}

/// Staff-only form for creating or editing a Client.
/// Parity with the portal's /clients/new/ and /clients/<id>/edit/ pages.
class ClientFormScreen extends StatefulWidget {
  const ClientFormScreen({super.key, this.client});

  final Client? client;

  bool get isEdit => client != null;

  @override
  State<ClientFormScreen> createState() => _ClientFormScreenState();
}

class _ClientFormScreenState extends State<ClientFormScreen> {
  final _form = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _company = TextEditingController();
  final _email = TextEditingController();
  final _phone = TextEditingController();
  final _vat = TextEditingController();
  final _address = TextEditingController();
  final _billingAddress = TextEditingController();
  final _notes = TextEditingController();
  String _customerType = 'home';
  String _carePlanTier = 'none';
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    final c = widget.client;
    if (c != null) {
      _name.text = c.name;
      _company.text = c.company;
      _email.text = c.email;
      _phone.text = c.phone;
      _vat.text = c.vatNumber;
      _address.text = c.address;
      _billingAddress.text = c.billingAddress;
      _notes.text = c.notes;
      _customerType = c.customerType.isEmpty ? 'home' : c.customerType;
      _carePlanTier = c.carePlanTier.isEmpty ? 'none' : c.carePlanTier;
    }
  }

  @override
  void dispose() {
    _name.dispose();
    _company.dispose();
    _email.dispose();
    _phone.dispose();
    _vat.dispose();
    _address.dispose();
    _billingAddress.dispose();
    _notes.dispose();
    super.dispose();
  }

  Map<String, dynamic> _payload() => {
        'name': _name.text.trim(),
        'company': _company.text.trim(),
        'email': _email.text.trim(),
        'phone': _phone.text.trim(),
        'customer_type': _customerType,
        'vat_number': _vat.text.trim(),
        'address': _address.text.trim(),
        'billing_address': _billingAddress.text.trim(),
        'care_plan_tier': _carePlanTier,
        'notes': _notes.text.trim(),
      };

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _saving = true);
    final messenger = ScaffoldMessenger.of(context);
    final router = GoRouter.of(context);
    final repo = ClientsRepository(context.read<ApiClient>());
    try {
      final saved = widget.isEdit
          ? await repo.update(widget.client!.id, _payload())
          : await repo.create(_payload());
      messenger.showSnackBar(
        SnackBar(
          content: Text(widget.isEdit
              ? 'Client updated.'
              : 'Client created.'),
        ),
      );
      router.go('/clients/${saved.id}');
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Save failed: $e')));
      setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.isEdit ? 'Edit client' : 'New client'),
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
              controller: _company,
              decoration: const InputDecoration(labelText: 'Company'),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              value: _customerType,
              decoration: const InputDecoration(labelText: 'Customer type'),
              items: const [
                DropdownMenuItem(value: 'home', child: Text('Home')),
                DropdownMenuItem(value: 'business', child: Text('Business')),
              ],
              onChanged: (v) {
                if (v != null) setState(() => _customerType = v);
              },
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _email,
              decoration: const InputDecoration(labelText: 'Email'),
              keyboardType: TextInputType.emailAddress,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _phone,
              decoration: const InputDecoration(labelText: 'Phone'),
              keyboardType: TextInputType.phone,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _address,
              maxLines: 3,
              decoration: const InputDecoration(labelText: 'Address'),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _billingAddress,
              maxLines: 3,
              decoration:
                  const InputDecoration(labelText: 'Billing address (optional)'),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _vat,
              decoration: const InputDecoration(labelText: 'VAT number'),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              value: _carePlanTier,
              decoration: const InputDecoration(labelText: 'Care plan tier'),
              items: const [
                DropdownMenuItem(value: 'none', child: Text('None')),
                DropdownMenuItem(
                    value: 'essential', child: Text('Essential')),
                DropdownMenuItem(
                    value: 'professional', child: Text('Professional')),
                DropdownMenuItem(
                    value: 'enterprise', child: Text('Enterprise')),
              ],
              onChanged: (v) {
                if (v != null) setState(() => _carePlanTier = v);
              },
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _notes,
              maxLines: 4,
              decoration: const InputDecoration(labelText: 'Notes'),
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
              label: Text(widget.isEdit ? 'Save changes' : 'Create client'),
            ),
          ],
        ),
      ),
    );
  }
}
