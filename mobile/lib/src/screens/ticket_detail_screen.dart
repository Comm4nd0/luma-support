import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../services/api_client.dart';

class TicketDetailScreen extends StatefulWidget {
  const TicketDetailScreen({super.key, required this.ticketId});

  final int ticketId;

  @override
  State<TicketDetailScreen> createState() => _TicketDetailScreenState();
}

class _TicketDetailScreenState extends State<TicketDetailScreen> {
  late Future<Map<String, dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _future = context.read<ApiClient>().getTicket(widget.ticketId);
  }

  void _refresh() {
    setState(() {
      _future = context.read<ApiClient>().getTicket(widget.ticketId);
    });
  }

  Future<void> _setStatus(String status) async {
    await context.read<ApiClient>().updateStatus(widget.ticketId, status);
    _refresh();
  }

  Future<void> _logTime() async {
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => const _LogTimeDialog(),
    );
    if (result == null) return;
    await context.read<ApiClient>().logTime(
      widget.ticketId,
      result['minutes'] as int,
      result['description'] as String,
    );
    _refresh();
  }

  Future<void> _addNote() async {
    final body = await showDialog<String>(
      context: context,
      builder: (_) => const _NoteDialog(),
    );
    if (body == null || body.trim().isEmpty) return;
    await context.read<ApiClient>().addNote(widget.ticketId, body.trim());
    _refresh();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Ticket #${widget.ticketId}')),
      body: FutureBuilder<Map<String, dynamic>>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          final t = snap.data ?? {};
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text(t['subject'] ?? '',
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
              const SizedBox(height: 6),
              Text('${t['client_name']} · ${t['priority']} · ${t['status']}'),
              const SizedBox(height: 12),
              Text(t['description'] ?? '', style: const TextStyle(height: 1.5)),
              const SizedBox(height: 24),
              Wrap(
                spacing: 8,
                children: [
                  for (final s in const ['assigned', 'in_progress', 'waiting', 'resolved', 'closed'])
                    OutlinedButton(
                      onPressed: () => _setStatus(s),
                      child: Text(s.replaceAll('_', ' ')),
                    ),
                ],
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: ElevatedButton.icon(
                      onPressed: _logTime,
                      icon: const Icon(Icons.timer),
                      label: const Text('Log time'),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: ElevatedButton.icon(
                      onPressed: _addNote,
                      icon: const Icon(Icons.note_add),
                      label: const Text('Add note'),
                    ),
                  ),
                ],
              ),
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
