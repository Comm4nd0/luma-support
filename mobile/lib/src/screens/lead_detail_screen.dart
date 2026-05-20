import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models/lead.dart';
import '../models/lead_activity.dart';
import '../repositories/leads_repository.dart';
import '../services/api_client.dart';

class LeadDetailScreen extends StatefulWidget {
  const LeadDetailScreen({super.key, required this.leadId});

  final int leadId;

  @override
  State<LeadDetailScreen> createState() => _LeadDetailScreenState();
}

class _LeadDetailScreenState extends State<LeadDetailScreen> {
  late Future<Lead> _future;

  LeadsRepository get _repo => LeadsRepository(context.read<ApiClient>());

  @override
  void initState() {
    super.initState();
    _future = _repo.get(widget.leadId);
  }

  Future<void> _refresh() async {
    setState(() => _future = _repo.get(widget.leadId));
  }

  Future<void> _advance(String stage) async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      await _repo.advance(widget.leadId, stage);
      messenger.showSnackBar(const SnackBar(content: Text('Stage updated.')));
      _refresh();
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Failed: $e')));
    }
  }

  Future<void> _convert() async {
    final messenger = ScaffoldMessenger.of(context);
    final router = GoRouter.of(context);
    try {
      final clientId = await _repo.convert(widget.leadId);
      messenger.showSnackBar(
        SnackBar(content: Text('Converted to client #$clientId.')),
      );
      router.go('/clients/$clientId');
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Failed: $e')));
    }
  }

  Future<void> _addActivity(Lead lead) async {
    final result = await showDialog<_ActivityDraft>(
      context: context,
      builder: (_) => const _LogActivityDialog(),
    );
    if (result == null) return;
    final messenger = ScaffoldMessenger.of(context);
    try {
      await _repo.addActivity(lead.id, result.kind, result.body);
      _refresh();
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Failed: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Lead'),
        actions: [
          IconButton(
            icon: const Icon(Icons.edit),
            onPressed: () async {
              final lead = await _future;
              if (!mounted) return;
              await context.push('/leads/${lead.id}/edit', extra: lead);
              _refresh();
            },
          ),
        ],
      ),
      body: FutureBuilder<Lead>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return Center(child: Text('Error: ${snap.error}'));
          }
          final lead = snap.data!;
          return RefreshIndicator(
            onRefresh: _refresh,
            child: ListView(
              padding: const EdgeInsets.all(12),
              children: [
                _HeaderCard(lead: lead),
                const SizedBox(height: 12),
                _ActionsCard(
                  lead: lead,
                  onAdvance: _advance,
                  onConvert: _convert,
                ),
                const SizedBox(height: 12),
                _PipelineCard(lead: lead),
                if (lead.interest.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Interest',
                            style: TextStyle(fontWeight: FontWeight.w600),
                          ),
                          const SizedBox(height: 6),
                          Text(lead.interest),
                        ],
                      ),
                    ),
                  ),
                ],
                const SizedBox(height: 12),
                _ActivitySection(
                  activities: lead.activities,
                  onAdd: () => _addActivity(lead),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _HeaderCard extends StatelessWidget {
  const _HeaderCard({required this.lead});
  final Lead lead;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              lead.name,
              style: Theme.of(context).textTheme.titleLarge,
            ),
            if (lead.company.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text(lead.company),
            ],
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 4,
              children: [
                Chip(label: Text(lead.stageDisplay)),
                Chip(label: Text(lead.sourceDisplay)),
                if (lead.isOverdue)
                  const Chip(
                    label: Text('Overdue'),
                    backgroundColor: Color(0x33FF6B6B),
                  ),
              ],
            ),
            if (lead.email.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text('Email: ${lead.email}'),
            ],
            if (lead.phone.isNotEmpty) Text('Phone: ${lead.phone}'),
          ],
        ),
      ),
    );
  }
}

class _ActionsCard extends StatelessWidget {
  const _ActionsCard({
    required this.lead,
    required this.onAdvance,
    required this.onConvert,
  });

  final Lead lead;
  final ValueChanged<String> onAdvance;
  final VoidCallback onConvert;

  @override
  Widget build(BuildContext context) {
    final hasClient = lead.convertedClientId != null;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Actions',
              style: TextStyle(fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final stage in const [
                  ['contacted', 'Contacted'],
                  ['qualified', 'Qualified'],
                  ['quoted', 'Quoted'],
                  ['lost', 'Lost'],
                  ['dormant', 'Dormant'],
                ])
                  OutlinedButton(
                    onPressed: lead.stage == stage[0]
                        ? null
                        : () => onAdvance(stage[0]),
                    child: Text(stage[1]),
                  ),
                if (hasClient)
                  ElevatedButton.icon(
                    onPressed: () =>
                        context.push('/clients/${lead.convertedClientId}'),
                    icon: const Icon(Icons.person),
                    label: const Text('View client'),
                  )
                else
                  ElevatedButton.icon(
                    onPressed: onConvert,
                    icon: const Icon(Icons.check),
                    label: const Text('Convert to client'),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _PipelineCard extends StatelessWidget {
  const _PipelineCard({required this.lead});
  final Lead lead;

  @override
  Widget build(BuildContext context) {
    final fmt = DateFormat('yyyy-MM-dd HH:mm');
    final rows = <List<String>>[
      ['Source', lead.sourceDisplay],
      if (lead.sourceDetail.isNotEmpty) ['Detail', lead.sourceDetail],
      if (lead.referringClientName.isNotEmpty)
        ['Referred by', lead.referringClientName],
      [
        'Estimated value',
        (lead.estimatedValue != null && lead.estimatedValue!.isNotEmpty)
            ? '£${lead.estimatedValue}'
            : '—',
      ],
      [
        'Next action',
        lead.nextActionAt != null ? fmt.format(lead.nextActionAt!) : '—',
      ],
      ['Assigned', lead.assignedToEmail.isEmpty ? '—' : lead.assignedToEmail],
      ['Created', DateFormat('yyyy-MM-dd').format(lead.createdAt)],
      if (lead.lostReason.isNotEmpty) ['Lost reason', lead.lostReason],
    ];
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Pipeline',
              style: TextStyle(fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 8),
            for (final r in rows)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    SizedBox(
                      width: 130,
                      child: Text(
                        r[0],
                        style: const TextStyle(color: Colors.grey),
                      ),
                    ),
                    Expanded(child: Text(r[1])),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _ActivitySection extends StatelessWidget {
  const _ActivitySection({required this.activities, required this.onAdd});

  final List<LeadActivity> activities;
  final VoidCallback onAdd;

  @override
  Widget build(BuildContext context) {
    final fmt = DateFormat('yyyy-MM-dd HH:mm');
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Expanded(
                  child: Text(
                    'Activity',
                    style: TextStyle(fontWeight: FontWeight.w600),
                  ),
                ),
                TextButton.icon(
                  onPressed: onAdd,
                  icon: const Icon(Icons.add),
                  label: const Text('Log'),
                ),
              ],
            ),
            const SizedBox(height: 4),
            if (activities.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 8),
                child: Text(
                  'No activity yet.',
                  style: TextStyle(color: Colors.grey),
                ),
              )
            else
              for (final a in activities)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  dense: true,
                  leading: const Icon(Icons.event_note),
                  title: Text(a.kindDisplay),
                  subtitle: Text(
                    '${fmt.format(a.occurredAt)}'
                    '${a.actorEmail.isNotEmpty ? ' · ${a.actorEmail}' : ''}'
                    '\n${a.body}',
                  ),
                  isThreeLine: a.body.isNotEmpty,
                ),
          ],
        ),
      ),
    );
  }
}

class _ActivityDraft {
  const _ActivityDraft(this.kind, this.body);
  final String kind;
  final String body;
}

class _LogActivityDialog extends StatefulWidget {
  const _LogActivityDialog();

  @override
  State<_LogActivityDialog> createState() => _LogActivityDialogState();
}

class _LogActivityDialogState extends State<_LogActivityDialog> {
  String _kind = 'note';
  final _body = TextEditingController();

  @override
  void dispose() {
    _body.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Log activity'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          DropdownButtonFormField<String>(
            value: _kind,
            items: const [
              DropdownMenuItem(value: 'note', child: Text('Note')),
              DropdownMenuItem(value: 'call', child: Text('Call')),
              DropdownMenuItem(value: 'email', child: Text('Email')),
              DropdownMenuItem(value: 'meeting', child: Text('Meeting')),
              DropdownMenuItem(value: 'quote_sent', child: Text('Quote sent')),
            ],
            onChanged: (v) => setState(() => _kind = v ?? 'note'),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _body,
            maxLines: 3,
            decoration: const InputDecoration(labelText: 'What happened'),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        ElevatedButton(
          onPressed: () {
            final body = _body.text.trim();
            if (body.isEmpty) return;
            Navigator.of(context).pop(_ActivityDraft(_kind, body));
          },
          child: const Text('Log'),
        ),
      ],
    );
  }
}
