import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../models/article.dart';
import '../models/ticket.dart';
import '../repositories/knowledge_repository.dart';
import '../repositories/tickets_repository.dart';
import '../services/api_client.dart';
import '../services/current_user.dart';
import 'widgets/ticket_tile.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../../src/widgets/luma_icon.dart';

class ClientDashboardScreen extends StatefulWidget {
  const ClientDashboardScreen({super.key});

  @override
  State<ClientDashboardScreen> createState() => _ClientDashboardScreenState();
}

class _ClientDashboardScreenState extends State<ClientDashboardScreen> {
  late Future<_DashboardData> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<_DashboardData> _load() async {
    final api = context.read<ApiClient>();
    final tickets = await TicketsRepository(api).list();
    final open = tickets
        .where((t) =>
            t.status != TicketStatus.resolved &&
            t.status != TicketStatus.closed)
        .toList();
    List<Article> articles = const [];
    try {
      final all = await KnowledgeRepository(api).list();
      articles = all.take(5).toList();
    } catch (_) {
      // KB is optional on the dashboard; never block the page on it.
    }
    return _DashboardData(open: open, articles: articles);
  }

  Future<void> _refresh() async {
    setState(() => _future = _load());
  }

  @override
  Widget build(BuildContext context) {
    final user = context.watch<CurrentUser>().user;
    return Scaffold(
      appBar: AppBar(
        title: Text(user == null ? 'Welcome' : 'Hi ${user.firstName.isEmpty ? user.email : user.firstName}'),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.push('/tickets/new'),
        icon: const LumaIcon(PhosphorIconsDuotone.plus),
        label: const Text('Submit a ticket'),
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
                _Section('Your open tickets', count: data.open.length),
                if (data.open.isEmpty)
                  const Padding(
                    padding: EdgeInsets.all(16),
                    child: Text('You have no open tickets — nice.',
                        style: TextStyle(color: Colors.grey)),
                  )
                else
                  for (final t in data.open)
                    TicketTile(
                      ticket: t,
                      onTap: () => context.push('/tickets/${t.id}'),
                    ),
                const SizedBox(height: 12),
                if (data.articles.isNotEmpty) ...[
                  const _Section('From the knowledge base'),
                  for (final a in data.articles)
                    Card(
                      margin: const EdgeInsets.only(bottom: 8),
                      child: ListTile(
                        title: Text(a.title),
                        subtitle: Text(a.category),
                        trailing: const LumaIcon(PhosphorIconsDuotone.caretRight),
                        onTap: () => context.push('/kb/${a.slug}'),
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

class _DashboardData {
  _DashboardData({required this.open, required this.articles});
  final List<Ticket> open;
  final List<Article> articles;
}

class _Section extends StatelessWidget {
  const _Section(this.label, {this.count});
  final String label;
  final int? count;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 12, 4, 8),
      child: Row(
        children: [
          Text(label, style: const TextStyle(fontWeight: FontWeight.w600)),
          if (count != null) ...[
            const SizedBox(width: 6),
            Text('($count)', style: const TextStyle(color: Colors.grey)),
          ],
        ],
      ),
    );
  }
}
