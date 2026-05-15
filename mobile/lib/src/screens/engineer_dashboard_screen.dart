import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../models/ticket.dart';
import '../repositories/tickets_repository.dart';
import '../services/api_client.dart';
import '../services/current_user.dart';
import 'widgets/ticket_tile.dart';

class EngineerDashboardScreen extends StatefulWidget {
  const EngineerDashboardScreen({super.key});

  @override
  State<EngineerDashboardScreen> createState() => _EngineerDashboardScreenState();
}

class _EngineerDashboardScreenState extends State<EngineerDashboardScreen> {
  late Future<_DashboardData> _future;

  TicketsRepository get _tickets => TicketsRepository(context.read<ApiClient>());

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<_DashboardData> _load() async {
    final all = await _tickets.list();
    return _DashboardData(
      slaWarnings: all.where((t) => t.isBreached || _withinWindow(t)).toList(),
      open: all
          .where((t) =>
              t.status != TicketStatus.resolved &&
              t.status != TicketStatus.closed)
          .toList(),
    );
  }

  bool _withinWindow(Ticket t) {
    final deadline = t.slaDeadline;
    if (deadline == null) return false;
    return deadline.difference(DateTime.now()).inMinutes <= 30;
  }

  Future<void> _refresh() async {
    setState(() => _future = _load());
  }

  @override
  Widget build(BuildContext context) {
    final user = context.watch<CurrentUser>().user;
    return Scaffold(
      appBar: AppBar(
        title: Text(user == null ? 'Dashboard' : 'Hi ${user.firstName.isEmpty ? user.email : user.firstName}'),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            onPressed: () => context.push('/tickets/new'),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<_DashboardData>(
          future: _future,
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snap.hasError) {
              return Center(child: Text('Error: ${snap.error}'));
            }
            final data = snap.data!;
            return ListView(
              padding: const EdgeInsets.all(12),
              children: [
                _SectionHeader(
                  'SLA warnings',
                  count: data.slaWarnings.length,
                  highlight: data.slaWarnings.isNotEmpty,
                ),
                if (data.slaWarnings.isEmpty)
                  const _EmptyHint('Nothing urgent right now.')
                else
                  for (final t in data.slaWarnings)
                    TicketTile(ticket: t, onTap: () => context.push('/tickets/${t.id}')),
                const SizedBox(height: 8),
                _SectionHeader('Open tickets', count: data.open.length),
                if (data.open.isEmpty)
                  const _EmptyHint('Inbox zero.')
                else
                  for (final t in data.open.take(20))
                    TicketTile(ticket: t, onTap: () => context.push('/tickets/${t.id}')),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _DashboardData {
  _DashboardData({required this.slaWarnings, required this.open});
  final List<Ticket> slaWarnings;
  final List<Ticket> open;
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader(this.label, {this.count, this.highlight = false});
  final String label;
  final int? count;
  final bool highlight;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 12, 4, 8),
      child: Row(
        children: [
          Text(label,
              style: TextStyle(
                fontWeight: FontWeight.w600,
                color: highlight ? Colors.redAccent : null,
              )),
          if (count != null) ...[
            const SizedBox(width: 6),
            Text('($count)',
                style: TextStyle(
                  color: highlight ? Colors.redAccent : Colors.grey,
                )),
          ],
        ],
      ),
    );
  }
}

class _EmptyHint extends StatelessWidget {
  const _EmptyHint(this.message);
  final String message;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.all(16),
        child: Text(message, style: const TextStyle(color: Colors.grey)),
      );
}
