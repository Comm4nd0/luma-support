import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/ticket.dart';
import '../repositories/tickets_repository.dart';
import '../services/api_client.dart';
import '../services/auth_service.dart';
import '../theme.dart';
import 'ticket_detail_screen.dart';
import 'ticket_create_screen.dart';

class TicketListScreen extends StatefulWidget {
  const TicketListScreen({super.key});

  @override
  State<TicketListScreen> createState() => _TicketListScreenState();
}

class _TicketListScreenState extends State<TicketListScreen> {
  late Future<List<Ticket>> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<List<Ticket>> _load() =>
      TicketsRepository(context.read<ApiClient>()).list();

  Future<void> _refresh() async {
    setState(() {
      _future = _load();
    });
  }

  Color _priorityColor(TicketPriority p) {
    switch (p) {
      case TicketPriority.critical:
        return const Color(0xFFF43F5E);
      case TicketPriority.high:
        return const Color(0xFFF97316);
      case TicketPriority.medium:
        return const Color(0xFFEAB308);
      case TicketPriority.low:
        return kMuted;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Tickets'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _refresh,
          ),
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () => context.read<AuthService>().logout(),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () async {
          await Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => const TicketCreateScreen()),
          );
          _refresh();
        },
        icon: const Icon(Icons.add),
        label: const Text('New ticket'),
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<List<Ticket>>(
          future: _future,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError) {
              return Center(child: Text('Error: ${snapshot.error}'));
            }
            final items = snapshot.data ?? const <Ticket>[];
            if (items.isEmpty) {
              return const Center(child: Text('No tickets yet.'));
            }
            return ListView.builder(
              padding: const EdgeInsets.all(12),
              itemCount: items.length,
              itemBuilder: (_, i) {
                final t = items[i];
                return Card(
                  margin: const EdgeInsets.only(bottom: 10),
                  child: ListTile(
                    onTap: () async {
                      await Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => TicketDetailScreen(ticketId: t.id),
                        ),
                      );
                      _refresh();
                    },
                    title:
                        Text(t.subject, maxLines: 1, overflow: TextOverflow.ellipsis),
                    subtitle: Text('${t.clientName} · #${t.id}'),
                    leading: CircleAvatar(
                      backgroundColor: _priorityColor(t.priority).withOpacity(0.18),
                      child: Text(
                        t.priority.name.substring(0, 1).toUpperCase(),
                        style: TextStyle(color: _priorityColor(t.priority)),
                      ),
                    ),
                    trailing: Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(t.status.name, style: const TextStyle(fontSize: 12)),
                        if (t.isBreached)
                          const Text('BREACHED',
                              style:
                                  TextStyle(color: Colors.redAccent, fontSize: 11)),
                      ],
                    ),
                  ),
                );
              },
            );
          },
        ),
      ),
    );
  }
}
