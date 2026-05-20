import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../models/lead.dart';
import '../repositories/leads_repository.dart';
import '../services/api_client.dart';

/// Loads a Lead before rendering the edit form — used when /leads/:id/edit
/// is hit directly without the Lead being passed via GoRouter's `extra`.
class LeadEditLoader extends StatefulWidget {
  const LeadEditLoader({super.key, required this.leadId});

  final int leadId;

  @override
  State<LeadEditLoader> createState() => _LeadEditLoaderState();
}

class _LeadEditLoaderState extends State<LeadEditLoader> {
  late Future<Lead> _future;

  @override
  void initState() {
    super.initState();
    _future =
        LeadsRepository(context.read<ApiClient>()).get(widget.leadId);
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Lead>(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }
        if (snap.hasError || snap.data == null) {
          return Scaffold(
            appBar: AppBar(title: const Text('Edit lead')),
            body: Center(child: Text('Error: ${snap.error}')),
          );
        }
        return LeadFormScreen(lead: snap.data!);
      },
    );
  }
}

class LeadFormScreen extends StatefulWidget {
  const LeadFormScreen({super.key, this.lead});

  final Lead? lead;

  bool get isEdit => lead != null;

  @override
  State<LeadFormScreen> createState() => _LeadFormScreenState();
}

class _LeadFormScreenState extends State<LeadFormScreen> {
  final _form = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _company = TextEditingController();
  final _email = TextEditingController();
  final _phone = TextEditingController();
  final _sourceDetail = TextEditingController();
  final _interest = TextEditingController();
  final _value = TextEditingController();
  String _stage = 'new';
  String _source = 'other';
  String _customerType = 'home';
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    final l = widget.lead;
    if (l != null) {
      _name.text = l.name;
      _company.text = l.company;
      _email.text = l.email;
      _phone.text = l.phone;
      _sourceDetail.text = l.sourceDetail;
      _interest.text = l.interest;
      _value.text = l.estimatedValue ?? '';
      _stage = l.stage.isEmpty ? 'new' : l.stage;
      _source = l.source.isEmpty ? 'other' : l.source;
      _customerType = l.customerType.isEmpty ? 'home' : l.customerType;
    }
  }

  @override
  void dispose() {
    _name.dispose();
    _company.dispose();
    _email.dispose();
    _phone.dispose();
    _sourceDetail.dispose();
    _interest.dispose();
    _value.dispose();
    super.dispose();
  }

  Map<String, dynamic> _payload() {
    final out = <String, dynamic>{
      'name': _name.text.trim(),
      'company': _company.text.trim(),
      'email': _email.text.trim(),
      'phone': _phone.text.trim(),
      'customer_type': _customerType,
      'source': _source,
      'source_detail': _sourceDetail.text.trim(),
      'interest': _interest.text.trim(),
      'stage': _stage,
    };
    final v = _value.text.trim();
    out['estimated_value'] = v.isEmpty ? null : v;
    return out;
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _saving = true);
    final messenger = ScaffoldMessenger.of(context);
    final router = GoRouter.of(context);
    final repo = LeadsRepository(context.read<ApiClient>());
    try {
      final saved = widget.isEdit
          ? await repo.update(widget.lead!.id, _payload())
          : await repo.create(_payload());
      messenger.showSnackBar(
        SnackBar(
          content:
              Text(widget.isEdit ? 'Lead updated.' : 'Lead created.'),
        ),
      );
      router.go('/leads/${saved.id}');
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Save failed: $e')));
      setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.isEdit ? 'Edit lead' : 'New lead'),
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
            DropdownButtonFormField<String>(
              value: _stage,
              decoration: const InputDecoration(labelText: 'Stage'),
              items: const [
                DropdownMenuItem(value: 'new', child: Text('New')),
                DropdownMenuItem(value: 'contacted', child: Text('Contacted')),
                DropdownMenuItem(
                    value: 'qualified', child: Text('Qualified')),
                DropdownMenuItem(value: 'quoted', child: Text('Quoted')),
                DropdownMenuItem(value: 'won', child: Text('Won')),
                DropdownMenuItem(value: 'lost', child: Text('Lost')),
                DropdownMenuItem(value: 'dormant', child: Text('Dormant')),
              ],
              onChanged: (v) {
                if (v != null) setState(() => _stage = v);
              },
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              value: _source,
              decoration: const InputDecoration(labelText: 'Source'),
              items: const [
                DropdownMenuItem(value: 'referral', child: Text('Referral')),
                DropdownMenuItem(value: 'website', child: Text('Website')),
                DropdownMenuItem(value: 'social', child: Text('Social')),
                DropdownMenuItem(
                    value: 'inbound_email', child: Text('Inbound email')),
                DropdownMenuItem(value: 'cold', child: Text('Cold outreach')),
                DropdownMenuItem(value: 'other', child: Text('Other')),
              ],
              onChanged: (v) {
                if (v != null) setState(() => _source = v);
              },
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _sourceDetail,
              decoration: const InputDecoration(
                labelText: 'Source detail',
                hintText: 'e.g. Facebook post 2026-04',
              ),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _value,
              decoration: const InputDecoration(
                labelText: 'Estimated value (£)',
              ),
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _interest,
              maxLines: 4,
              decoration: const InputDecoration(
                labelText: 'Interest (what do they need?)',
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
              label:
                  Text(widget.isEdit ? 'Save changes' : 'Create lead'),
            ),
          ],
        ),
      ),
    );
  }
}
