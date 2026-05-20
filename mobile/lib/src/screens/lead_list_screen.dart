import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models/lead.dart';
import '../repositories/leads_repository.dart';
import '../services/api_client.dart';

/// Staff-only list of leads — parity with the portal's /leads/ page.
class LeadListScreen extends StatefulWidget {
  const LeadListScreen({super.key});

  @override
  State<LeadListScreen> createState() => _LeadListScreenState();
}

class _LeadListScreenState extends State<LeadListScreen> {
  late Future<List<Lead>> _future;
  String _stageFilter = '';
  String _filter = '';

  LeadsRepository get _repo => LeadsRepository(context.read<ApiClient>());

  @override
  void initState() {
    super.initState();
    _future = _repo.list();
  }

  Future<void> _refresh() async {
    setState(
      () => _future = _repo.list(stage: _stageFilter.isEmpty ? null : _stageFilter),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Leads'),
        actions: [
          PopupMenuButton<String>(
            tooltip: 'Filter by stage',
            initialValue: _stageFilter,
            onSelected: (v) {
              setState(() => _stageFilter = v);
              _refresh();
            },
            itemBuilder: (_) => const [
              PopupMenuItem(value: '', child: Text('All stages')),
              PopupMenuItem(value: 'new', child: Text('New')),
              PopupMenuItem(value: 'contacted', child: Text('Contacted')),
              PopupMenuItem(value: 'qualified', child: Text('Qualified')),
              PopupMenuItem(value: 'quoted', child: Text('Quoted')),
              PopupMenuItem(value: 'won', child: Text('Won')),
              PopupMenuItem(value: 'lost', child: Text('Lost')),
              PopupMenuItem(value: 'dormant', child: Text('Dormant')),
            ],
            icon: const Icon(Icons.filter_list),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () async {
          await context.push('/leads/new');
          _refresh();
        },
        icon: const Icon(Icons.add),
        label: const Text('New lead'),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: TextField(
              decoration: const InputDecoration(
                prefixIcon: Icon(Icons.search),
                hintText: 'Filter by name or company',
              ),
              onChanged: (v) => setState(() => _filter = v.toLowerCase()),
            ),
          ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: _refresh,
              child: FutureBuilder<List<Lead>>(
                future: _future,
                builder: (context, snap) {
                  if (snap.connectionState != ConnectionState.done) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  if (snap.hasError) {
                    return Center(child: Text('Error: ${snap.error}'));
                  }
                  final items = (snap.data ?? const <Lead>[])
                      .where((l) =>
                          _filter.isEmpty ||
                          l.name.toLowerCase().contains(_filter) ||
                          l.company.toLowerCase().contains(_filter))
                      .toList();
                  if (items.isEmpty) {
                    return const Center(child: Text('No leads.'));
                  }
                  return ListView.builder(
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    itemCount: items.length,
                    itemBuilder: (_, i) => _LeadCard(lead: items[i]),
                  );
                },
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _LeadCard extends StatelessWidget {
  const _LeadCard({required this.lead});
  final Lead lead;

  @override
  Widget build(BuildContext context) {
    final dateFmt = DateFormat('yyyy-MM-dd');
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: CircleAvatar(
          child: Text(
            lead.name.isNotEmpty ? lead.name[0].toUpperCase() : '?',
          ),
        ),
        title: Text(lead.name),
        subtitle: Text([
          if (lead.company.isNotEmpty) lead.company,
          lead.stageDisplay,
          if (lead.estimatedValue != null && lead.estimatedValue!.isNotEmpty)
            '£${lead.estimatedValue}',
          if (lead.nextActionAt != null)
            'next ${dateFmt.format(lead.nextActionAt!)}',
        ].join(' · ')),
        trailing: lead.isOverdue
            ? const Icon(Icons.warning_amber, color: Colors.redAccent)
            : const Icon(Icons.chevron_right),
        onTap: () => context.push('/leads/${lead.id}'),
      ),
    );
  }
}
