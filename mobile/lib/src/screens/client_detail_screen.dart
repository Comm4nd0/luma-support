import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../models/client.dart';
import '../models/ticket.dart';
import '../repositories/clients_repository.dart';
import '../repositories/tickets_repository.dart';
import '../services/api_client.dart';
import 'widgets/ticket_tile.dart';

class ClientDetailScreen extends StatefulWidget {
  const ClientDetailScreen({super.key, required this.clientId});

  final int clientId;

  @override
  State<ClientDetailScreen> createState() => _ClientDetailScreenState();
}

class _ClientDetailScreenState extends State<ClientDetailScreen> {
  late Future<_ClientDetailData> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<_ClientDetailData> _load() async {
    final api = context.read<ApiClient>();
    final client = await ClientsRepository(api).get(widget.clientId);
    // Tickets aren't nested in the client serializer, so fetch separately.
    // The viewset filters by `client` query param.
    final tickets = await TicketsRepository(api).list();
    return _ClientDetailData(
      client: client,
      tickets: tickets.where((t) => t.clientId == widget.clientId).toList(),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Client')),
      body: FutureBuilder<_ClientDetailData>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return Center(child: Text('Error: ${snap.error}'));
          }
          final data = snap.data!;
          final c = data.client;
          return DefaultTabController(
            length: 3,
            child: Column(
              children: [
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(c.name,
                          style: const TextStyle(
                              fontSize: 22, fontWeight: FontWeight.w600)),
                      if (c.company.isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 2),
                          child: Text(c.company,
                              style: const TextStyle(color: Colors.grey)),
                        ),
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 8,
                        runSpacing: 4,
                        children: [
                          if (c.email.isNotEmpty) Chip(label: Text(c.email)),
                          if (c.phone.isNotEmpty) Chip(label: Text(c.phone)),
                          Chip(label: Text('Plan: ${c.carePlanTier}')),
                        ],
                      ),
                    ],
                  ),
                ),
                const TabBar(
                  tabs: [
                    Tab(text: 'Systems'),
                    Tab(text: 'Contacts'),
                    Tab(text: 'Tickets'),
                  ],
                ),
                Expanded(
                  child: TabBarView(
                    children: [
                      _systemsTab(c),
                      _contactsTab(c),
                      _ticketsTab(data.tickets),
                    ],
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _systemsTab(Client c) {
    if (c.systems.isEmpty) {
      return const _EmptyState('No systems on file.');
    }
    return ListView(
      padding: const EdgeInsets.all(12),
      children: [
        for (final s in c.systems)
          Card(
            margin: const EdgeInsets.only(bottom: 8),
            child: ListTile(
              leading: const Icon(Icons.memory),
              title: Text(s.name),
              subtitle: Text('${s.type} · ${s.description}',
                  maxLines: 2, overflow: TextOverflow.ellipsis),
            ),
          ),
      ],
    );
  }

  Widget _contactsTab(Client c) {
    if (c.contacts.isEmpty) {
      return const _EmptyState('No contacts on file.');
    }
    return ListView(
      padding: const EdgeInsets.all(12),
      children: [
        for (final ct in c.contacts)
          Card(
            margin: const EdgeInsets.only(bottom: 8),
            child: ListTile(
              leading: CircleAvatar(child: Text(ct.name.isNotEmpty ? ct.name[0] : '?')),
              title: Text(ct.name),
              subtitle: Text([
                if (ct.title.isNotEmpty) ct.title,
                if (ct.email.isNotEmpty) ct.email,
                if (ct.phone.isNotEmpty) ct.phone,
              ].join(' · ')),
              trailing: ct.isPrimary ? const Chip(label: Text('Primary')) : null,
            ),
          ),
      ],
    );
  }

  Widget _ticketsTab(List<Ticket> tickets) {
    if (tickets.isEmpty) {
      return const _EmptyState('No tickets for this client.');
    }
    return ListView(
      padding: const EdgeInsets.all(12),
      children: [
        for (final t in tickets)
          TicketTile(ticket: t, onTap: () => context.push('/tickets/${t.id}')),
      ],
    );
  }
}

class _ClientDetailData {
  _ClientDetailData({required this.client, required this.tickets});
  final Client client;
  final List<Ticket> tickets;
}

class _EmptyState extends StatelessWidget {
  const _EmptyState(this.message);
  final String message;
  @override
  Widget build(BuildContext context) => Center(
        child: Text(message, style: const TextStyle(color: Colors.grey)),
      );
}
