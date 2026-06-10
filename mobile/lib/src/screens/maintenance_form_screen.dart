import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models/maintenance_schedule.dart';
import '../repositories/maintenance_repository.dart';
import '../services/api_client.dart';
import 'widgets/client_picker.dart';

/// Staff form for creating or editing a maintenance schedule.
/// Parity with the portal's /schedules/new/ and /schedules/<id>/edit/ pages.
class MaintenanceFormScreen extends StatefulWidget {
  const MaintenanceFormScreen({super.key, this.schedule});

  final MaintenanceSchedule? schedule;

  bool get isEdit => schedule != null;

  @override
  State<MaintenanceFormScreen> createState() => _MaintenanceFormScreenState();
}

class _MaintenanceFormScreenState extends State<MaintenanceFormScreen> {
  final _form = GlobalKey<FormState>();
  final _subject = TextEditingController();
  final _description = TextEditingController();
  int? _clientId;
  String _clientLabel = '';
  MaintenanceCadence _cadence = MaintenanceCadence.monthly;
  DateTime? _nextRunAt;
  bool _active = true;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    final s = widget.schedule;
    if (s != null) {
      _subject.text = s.templateSubject;
      _description.text = s.templateDescription;
      _clientId = s.clientId;
      _clientLabel = s.clientName;
      _cadence = s.cadence == MaintenanceCadence.unknown
          ? MaintenanceCadence.monthly
          : s.cadence;
      _nextRunAt = s.nextRunAt;
      _active = s.active;
    }
  }

  @override
  void dispose() {
    _subject.dispose();
    _description.dispose();
    super.dispose();
  }

  Future<void> _pickClient() async {
    final picked = await showClientPicker(context, context.read<ApiClient>());
    if (picked != null && mounted) {
      setState(() {
        _clientId = picked.id;
        _clientLabel = picked.name.isEmpty ? picked.company : picked.name;
      });
    }
  }

  Future<void> _pickDate() async {
    final now = DateTime.now();
    final initial = _nextRunAt ?? now.add(const Duration(days: 30));
    final picked = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: now.subtract(const Duration(days: 30)),
      lastDate: now.add(const Duration(days: 365 * 5)),
    );
    if (picked != null && mounted) {
      setState(() => _nextRunAt = picked);
    }
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    if (_clientId == null) {
      _snack('Pick a client.');
      return;
    }
    if (_nextRunAt == null) {
      _snack('Pick a next-run date.');
      return;
    }
    setState(() => _saving = true);
    final messenger = ScaffoldMessenger.of(context);
    final router = GoRouter.of(context);
    final repo = MaintenanceRepository(context.read<ApiClient>());
    try {
      if (widget.isEdit) {
        await repo.update(
          widget.schedule!.id,
          clientId: _clientId!,
          systemId: widget.schedule!.systemId,
          cadence: _cadence.name,
          nextRunAt: _nextRunAt!,
          templateSubject: _subject.text.trim(),
          templateDescription: _description.text.trim(),
          priority: widget.schedule!.priority,
          defaultAssigneeId: widget.schedule!.defaultAssigneeId,
          active: _active,
        );
      } else {
        await repo.create(
          clientId: _clientId!,
          cadence: _cadence.name,
          nextRunAt: _nextRunAt!,
          templateSubject: _subject.text.trim(),
          templateDescription: _description.text.trim(),
          active: _active,
        );
      }
      messenger.showSnackBar(
        SnackBar(
          content: Text(widget.isEdit
              ? 'Schedule updated.'
              : 'Maintenance schedule created.'),
        ),
      );
      router.go('/maintenance');
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Save failed: $e')));
      setState(() => _saving = false);
    }
  }

  void _snack(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title:
            Text(widget.isEdit ? 'Edit schedule' : 'New maintenance schedule'),
      ),
      body: Form(
        key: _form,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Card(
              child: ListTile(
                leading: const Icon(Icons.business_outlined),
                title: Text(_clientId == null ? 'Pick a client' : _clientLabel),
                trailing: const Icon(Icons.chevron_right),
                onTap: _pickClient,
              ),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _subject,
              decoration: const InputDecoration(
                labelText: 'Ticket subject template',
              ),
              validator: (v) =>
                  v == null || v.trim().isEmpty ? 'Required' : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _description,
              maxLines: 4,
              decoration: const InputDecoration(
                labelText: 'Ticket description template',
              ),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<MaintenanceCadence>(
              value: _cadence,
              decoration: const InputDecoration(labelText: 'Cadence'),
              items: [
                for (final c in const [
                  MaintenanceCadence.weekly,
                  MaintenanceCadence.monthly,
                  MaintenanceCadence.quarterly,
                  MaintenanceCadence.biannual,
                  MaintenanceCadence.annual,
                ])
                  DropdownMenuItem(value: c, child: Text(cadenceLabel(c))),
              ],
              onChanged: (v) {
                if (v != null) setState(() => _cadence = v);
              },
            ),
            const SizedBox(height: 12),
            Card(
              child: ListTile(
                leading: const Icon(Icons.calendar_today_outlined),
                title: Text(_nextRunAt == null
                    ? 'Next run date'
                    : DateFormat.yMMMd().format(_nextRunAt!)),
                trailing: const Icon(Icons.chevron_right),
                onTap: _pickDate,
              ),
            ),
            const SizedBox(height: 12),
            ListTile(
              onTap: () => setState(() => _active = !_active),
              title: const Text('Active'),
              subtitle: const Text(
                'Paused schedules stop generating tickets on their cadence.',
              ),
              trailing: CupertinoSwitch(
                value: _active,
                onChanged: (v) => setState(() => _active = v),
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
              label: Text(widget.isEdit ? 'Save changes' : 'Create schedule'),
            ),
          ],
        ),
      ),
    );
  }
}
