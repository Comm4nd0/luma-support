import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

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
  late Future<List<dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _future = context.read<ApiClient>().listTickets();
  }

  Future<void> _refresh() async {
    setState(() {
      _future = context.read<ApiClient>().listTickets();
    });
  }

  Color _priorityColor(String p) {
    switch (p) {
      case 'critical':
        return const Color(0xFFF43F5E);
      case 'high':
        return const Color(0xFFF97316);
      case 'medium':
        return const Color(0xFFEAB308);
      default:
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
        child: FutureBuilder<List<dynamic>>(
          future: _future,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError) {
              return Center(child: Text('Error: ${snapshot.error}'));
            }
            final items = snapshot.data ?? [];
            // Sorted by SLA urgency (server returns deadline-asc).
            return ListView.builder(
              padding: const EdgeInsets.all(12),
              itemCount: items.length,
              itemBuilder: (_, i) {
                final t = items[i] as Map<String, dynamic>;
                final breached = t['is_breached'] == true;
                return Card(
                  margin: const EdgeInsets.only(bottom: 10),
                  child: ListTile(
                    onTap: () async {
                      await Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => TicketDetailScreen(ticketId: t['id'] as int),
                        ),
                      );
                      _refresh();
                    },
                    title: Text(t['subject'] ?? '',
                        maxLines: 1, overflow: TextOverflow.ellipsis),
                    subtitle: Text('${t['client_name'] ?? ''} · #${t['id']}'),
                    leading: CircleAvatar(
                      backgroundColor: _priorityColor(t['priority'] as String? ?? 'low')
                          .withOpacity(0.18),
                      child: Text(
                        (t['priority'] as String? ?? '')
                            .substring(0, 1)
                            .toUpperCase(),
                        style: TextStyle(color: _priorityColor(t['priority'] as String? ?? 'low')),
                      ),
                    ),
                    trailing: Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(t['status'] ?? '', style: const TextStyle(fontSize: 12)),
                        if (breached)
                          const Text('BREACHED',
                              style: TextStyle(color: Colors.redAccent, fontSize: 11)),
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
