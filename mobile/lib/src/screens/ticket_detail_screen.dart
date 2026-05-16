import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../models/ticket.dart';
import '../repositories/tickets_repository.dart';
import '../services/api_client.dart';
import '../services/current_user.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../../src/widgets/luma_icon.dart';
import 'signature_screen.dart';
import 'ticket_timer_screen.dart';

class TicketDetailScreen extends StatefulWidget {
  const TicketDetailScreen({super.key, required this.ticketId});

  final int ticketId;

  @override
  State<TicketDetailScreen> createState() => _TicketDetailScreenState();
}

class _TicketDetailScreenState extends State<TicketDetailScreen> {
  late Future<Ticket> _future;

  TicketsRepository get _repo => TicketsRepository(context.read<ApiClient>());

  @override
  void initState() {
    super.initState();
    _future = _repo.get(widget.ticketId);
  }

  void _refresh() {
    setState(() {
      _future = _repo.get(widget.ticketId);
    });
  }

  Future<void> _setStatus(TicketStatus status) async {
    await _repo.setStatus(widget.ticketId, status);
    _refresh();
  }

  Future<void> _logTime() async {
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => const _LogTimeDialog(),
    );
    if (result == null) return;
    await _repo.logTime(
      widget.ticketId,
      minutes: result['minutes'] as int,
      description: result['description'] as String,
    );
    _refresh();
  }

  Future<void> _addNote() async {
    final body = await showDialog<String>(
      context: context,
      builder: (_) => const _NoteDialog(),
    );
    if (body == null || body.trim().isEmpty) return;
    await _repo.addNote(widget.ticketId, body.trim());
    _refresh();
  }

  Future<void> _runTimer() async {
    final logged = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => TicketTimerScreen(ticketId: widget.ticketId),
      ),
    );
    if (logged == true) _refresh();
  }

  Future<void> _attachPhoto({required ImageSource source}) async {
    final picker = ImagePicker();
    final picked = await picker.pickImage(source: source, imageQuality: 80);
    if (picked == null) return;
    try {
      await _repo.uploadAttachment(widget.ticketId, File(picked.path));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Photo uploaded.')),
        );
        _refresh();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Upload failed: $e')),
        );
      }
    }
  }

  Future<void> _photoSheet() async {
    final source = await showModalBottomSheet<ImageSource>(
      context: context,
      builder: (_) => SafeArea(
        child: Wrap(
          children: [
            ListTile(
              leading: const Icon(Icons.camera_alt_outlined),
              title: const Text('Take a photo'),
              onTap: () => Navigator.pop(context, ImageSource.camera),
            ),
            ListTile(
              leading: const Icon(Icons.photo_library_outlined),
              title: const Text('Pick from gallery'),
              onTap: () => Navigator.pop(context, ImageSource.gallery),
            ),
          ],
        ),
      ),
    );
    if (source != null) await _attachPhoto(source: source);
  }

  Future<void> _captureSignature() async {
    final uploaded = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => SignatureScreen(ticketId: widget.ticketId),
      ),
    );
    if (uploaded == true) _refresh();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Ticket #${widget.ticketId}')),
      body: FutureBuilder<Ticket>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return Center(child: Text('Error: ${snap.error}'));
          }
          final t = snap.data!;
          final isStaff = context.watch<CurrentUser>().isStaff;
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text(t.subject,
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
              const SizedBox(height: 6),
              Text('${t.clientName} · ${t.priority.name} · ${t.status.name}'),
              const SizedBox(height: 12),
              Text(t.description, style: const TextStyle(height: 1.5)),
              const SizedBox(height: 24),
              if (isStaff) ...[
                Wrap(
                  spacing: 8,
                  children: [
                    for (final s in const [
                      TicketStatus.assigned,
                      TicketStatus.inProgress,
                      TicketStatus.waiting,
                      TicketStatus.resolved,
                      TicketStatus.closed,
                    ])
                      OutlinedButton(
                        onPressed: () => _setStatus(s),
                        child: Text(statusToWire(s).replaceAll('_', ' ')),
                      ),
                  ],
                ),
                const SizedBox(height: 16),
              ],
              Row(
                children: [
                  if (isStaff) ...[
                    Expanded(
                      child: ElevatedButton.icon(
                        onPressed: _logTime,
                        icon: const LumaIcon(PhosphorIconsDuotone.timer),
                        label: const Text('Log time'),
                      ),
                    ),
                    const SizedBox(width: 8),
                  ],
                  Expanded(
                    child: ElevatedButton.icon(
                      onPressed: _addNote,
                      icon: const LumaIcon(PhosphorIconsDuotone.notePencil),
                      label: const Text('Add note'),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  if (isStaff) ...[
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: _runTimer,
                        icon: const Icon(Icons.timer_outlined),
                        label: const Text('Start timer'),
                      ),
                    ),
                    const SizedBox(width: 8),
                  ],
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: _photoSheet,
                      icon: const Icon(Icons.photo_camera_outlined),
                      label: const Text('Photo'),
                    ),
                  ),
                ],
              ),
              if (isStaff) ...[
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  onPressed: _captureSignature,
                  icon: const Icon(Icons.gesture),
                  label: const Text('Capture signature'),
                ),
              ],
            ],
          );
        },
      ),
    );
  }
}

class _LogTimeDialog extends StatefulWidget {
  const _LogTimeDialog();

  @override
  State<_LogTimeDialog> createState() => _LogTimeDialogState();
}

class _LogTimeDialogState extends State<_LogTimeDialog> {
  final _minutes = TextEditingController();
  final _description = TextEditingController();

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Log time'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          TextField(
            controller: _minutes,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(labelText: 'Minutes'),
          ),
          TextField(
            controller: _description,
            decoration: const InputDecoration(labelText: 'Description'),
          ),
        ],
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        ElevatedButton(
          onPressed: () {
            final m = int.tryParse(_minutes.text) ?? 0;
            if (m <= 0) return;
            Navigator.pop(context, {
              'minutes': m,
              'description': _description.text,
            });
          },
          child: const Text('Save'),
        ),
      ],
    );
  }
}

class _NoteDialog extends StatefulWidget {
  const _NoteDialog();

  @override
  State<_NoteDialog> createState() => _NoteDialogState();
}

class _NoteDialogState extends State<_NoteDialog> {
  final _body = TextEditingController();

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Add note'),
      content: TextField(
        controller: _body,
        maxLines: 4,
        decoration: const InputDecoration(labelText: 'Note'),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        ElevatedButton(
          onPressed: () => Navigator.pop(context, _body.text),
          child: const Text('Save'),
        ),
      ],
    );
  }
}
