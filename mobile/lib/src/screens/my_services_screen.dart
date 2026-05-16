import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models/system.dart';
import '../models/ticket.dart';
import '../repositories/clients_repository.dart';
import '../repositories/tickets_repository.dart';
import '../services/api_client.dart';
import '../services/current_user.dart';

/// Client-facing parity of the portal's `/my-services/` page: each of the
/// caller's Systems with health pill + last-checked age, and any open
/// tickets that reference those systems.
class MyServicesScreen extends StatefulWidget {
  const MyServicesScreen({super.key});

  @override
  State<MyServicesScreen> createState() => _MyServicesScreenState();
}

class _MyServicesScreenState extends State<MyServicesScreen> {
  late Future<_Data> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<_Data> _load() async {
    final api = context.read<ApiClient>();
    final user = context.read<CurrentUser>().user;
    final clientId = user?.clientId;
    if (clientId == null) {
      return _Data(systems: const [], openTickets: const []);
    }
    final client = await ClientsRepository(api).get(clientId);
    final tickets = await TicketsRepository(api).list();
    final open = tickets
        .where((t) =>
            t.status != TicketStatus.resolved &&
            t.status != TicketStatus.closed)
        .toList();
    return _Data(systems: client.systems, openTickets: open);
  }

  Future<void> _refresh() async {
    setState(() => _future = _load());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Your services')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<_Data>(
          future: _future,
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snap.hasError) {
              return Center(child: Text('Error: ${snap.error}'));
            }
            final data = snap.data!;
            if (data.systems.isEmpty) {
              return const Center(
                child: Padding(
                  padding: EdgeInsets.all(24),
                  child: Text(
                    'No systems registered yet. Open a ticket if something\'s '
                    'missing.',
                    textAlign: TextAlign.center,
                  ),
                ),
              );
            }
            return ListView(
              padding: const EdgeInsets.all(12),
              children: [
                for (final s in data.systems) _SystemCard(system: s),
                if (data.openTickets.isNotEmpty) ...[
                  const Padding(
                    padding: EdgeInsets.fromLTRB(4, 16, 4, 8),
                    child: Text(
                      'Open tickets',
                      style: TextStyle(fontWeight: FontWeight.w600),
                    ),
                  ),
                  for (final t in data.openTickets)
                    Card(
                      margin: const EdgeInsets.only(bottom: 8),
                      child: ListTile(
                        title: Text(t.subject),
                        subtitle: Text('#${t.id}'),
                        onTap: () => context.push('/tickets/${t.id}'),
                      ),
                    ),
                ],
              ],
            );
          },
        ),
      ),
    );
  }
}

class _Data {
  _Data({required this.systems, required this.openTickets});
  final List<ClientSystem> systems;
  final List<Ticket> openTickets;
}

class _SystemCard extends StatelessWidget {
  const _SystemCard({required this.system});

  final ClientSystem system;

  Color _healthColor(BuildContext context) {
    switch (system.health) {
      case SystemHealth.ok:
        return Colors.green;
      case SystemHealth.degraded:
        return Colors.amber;
      case SystemHealth.down:
        return Colors.redAccent;
      case SystemHealth.unknown:
        return Colors.grey;
    }
  }

  @override
  Widget build(BuildContext context) {
    final color = _healthColor(context);
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        system.name,
                        style: const TextStyle(fontWeight: FontWeight.w600),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        system.type,
                        style: const TextStyle(color: Colors.grey, fontSize: 12),
                      ),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    healthLabel(system.health),
                    style: TextStyle(color: color, fontWeight: FontWeight.w600),
                  ),
                ),
              ],
            ),
            if (system.devicesOnline != null || system.devicesOffline != null) ...[
              const SizedBox(height: 8),
              Text(
                '${system.devicesOnline ?? 0} online · ${system.devicesOffline ?? 0} offline',
                style: const TextStyle(color: Colors.grey, fontSize: 12),
              ),
            ],
            if (system.lastCheckedAt != null) ...[
              const SizedBox(height: 4),
              Text(
                'Last checked ${DateFormat.yMMMd().add_jm().format(system.lastCheckedAt!.toLocal())}',
                style: const TextStyle(color: Colors.grey, fontSize: 12),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
