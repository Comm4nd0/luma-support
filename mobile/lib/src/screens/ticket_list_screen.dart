import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../models/ticket.dart';
import '../repositories/tickets_repository.dart';
import '../services/api_client.dart';
import 'widgets/ticket_tile.dart';

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
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () async {
          await context.push('/tickets/new');
          if (mounted) _refresh();
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
                return TicketTile(
                  ticket: t,
                  onTap: () async {
                    await context.push('/tickets/${t.id}');
                    if (mounted) _refresh();
                  },
                );
              },
            );
          },
        ),
      ),
    );
  }
}
