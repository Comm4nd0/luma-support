import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../models/quote.dart';
import '../repositories/quotes_repository.dart';
import '../services/api_client.dart';

class QuoteListScreen extends StatefulWidget {
  const QuoteListScreen({super.key});

  @override
  State<QuoteListScreen> createState() => _QuoteListScreenState();
}

class _QuoteListScreenState extends State<QuoteListScreen> {
  late Future<List<Quote>> _future;
  String _statusFilter = '';

  QuotesRepository get _repo => QuotesRepository(context.read<ApiClient>());

  @override
  void initState() {
    super.initState();
    _future = _repo.list();
  }

  Future<void> _refresh() async {
    setState(
      () => _future =
          _repo.list(status: _statusFilter.isEmpty ? null : _statusFilter),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Quotes'),
        actions: [
          PopupMenuButton<String>(
            tooltip: 'Filter by status',
            initialValue: _statusFilter,
            onSelected: (v) {
              setState(() => _statusFilter = v);
              _refresh();
            },
            itemBuilder: (_) => const [
              PopupMenuItem(value: '', child: Text('All statuses')),
              PopupMenuItem(value: 'draft', child: Text('Draft')),
              PopupMenuItem(value: 'sent', child: Text('Sent')),
              PopupMenuItem(value: 'accepted', child: Text('Accepted')),
              PopupMenuItem(value: 'rejected', child: Text('Rejected')),
              PopupMenuItem(value: 'expired', child: Text('Expired')),
            ],
            icon: const Icon(Icons.filter_list),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<List<Quote>>(
          future: _future,
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snap.hasError) {
              return Center(child: Text('Error: ${snap.error}'));
            }
            final items = snap.data ?? const <Quote>[];
            if (items.isEmpty) {
              return const Center(child: Text('No quotes.'));
            }
            return ListView.builder(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              itemCount: items.length,
              itemBuilder: (_, i) {
                final q = items[i];
                return Card(
                  margin: const EdgeInsets.only(bottom: 8),
                  child: ListTile(
                    title: Text(q.number),
                    subtitle: Text(
                      [
                        q.recipientName.isEmpty ? '—' : q.recipientName,
                        q.statusDisplay,
                        '${q.currency} ${q.total}',
                      ].join(' · '),
                    ),
                    trailing: q.isExpired
                        ? const Icon(Icons.timer_off, color: Colors.redAccent)
                        : const Icon(Icons.chevron_right),
                    onTap: () => context.push('/quotes/${q.id}'),
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
