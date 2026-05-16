import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../models/client.dart';
import '../repositories/clients_repository.dart';
import '../services/api_client.dart';
import '../services/current_user.dart';

/// Staff-only list of clients. Parity with the portal's /clients/ page.
class ClientListScreen extends StatefulWidget {
  const ClientListScreen({super.key});

  @override
  State<ClientListScreen> createState() => _ClientListScreenState();
}

class _ClientListScreenState extends State<ClientListScreen> {
  late Future<List<Client>> _future;
  String _filter = '';

  ClientsRepository get _repo => ClientsRepository(context.read<ApiClient>());

  @override
  void initState() {
    super.initState();
    _future = _repo.list();
  }

  Future<void> _refresh() async {
    setState(() => _future = _repo.list());
  }

  @override
  Widget build(BuildContext context) {
    final isStaff = context.watch<CurrentUser>().isStaff;
    return Scaffold(
      appBar: AppBar(title: const Text('Clients')),
      floatingActionButton: isStaff
          ? FloatingActionButton.extended(
              onPressed: () async {
                await context.push('/clients/new');
                _refresh();
              },
              icon: const Icon(Icons.add),
              label: const Text('New client'),
            )
          : null,
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
              child: FutureBuilder<List<Client>>(
                future: _future,
                builder: (context, snap) {
                  if (snap.connectionState != ConnectionState.done) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  if (snap.hasError) {
                    return Center(child: Text('Error: ${snap.error}'));
                  }
                  final items = (snap.data ?? const <Client>[])
                      .where((c) =>
                          _filter.isEmpty ||
                          c.name.toLowerCase().contains(_filter) ||
                          c.company.toLowerCase().contains(_filter))
                      .toList();
                  if (items.isEmpty) {
                    return const Center(child: Text('No clients.'));
                  }
                  return ListView.builder(
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    itemCount: items.length,
                    itemBuilder: (_, i) {
                      final c = items[i];
                      return Card(
                        margin: const EdgeInsets.only(bottom: 8),
                        child: ListTile(
                          leading: CircleAvatar(
                            child: Text(c.name.isNotEmpty
                                ? c.name[0].toUpperCase()
                                : '?'),
                          ),
                          title: Text(c.name.isEmpty ? c.company : c.name),
                          subtitle: Text([
                            if (c.company.isNotEmpty && c.company != c.name)
                              c.company,
                            'Plan: ${c.carePlanTier}',
                            if (c.openTicketCount > 0)
                              '${c.openTicketCount} open',
                          ].join(' · ')),
                          trailing: const Icon(Icons.chevron_right),
                          onTap: () => context.push('/clients/${c.id}'),
                        ),
                      );
                    },
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
