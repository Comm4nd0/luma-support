import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models/quote.dart';
import '../repositories/quotes_repository.dart';
import '../services/api_client.dart';

class QuoteDetailScreen extends StatefulWidget {
  const QuoteDetailScreen({super.key, required this.quoteId});

  final int quoteId;

  @override
  State<QuoteDetailScreen> createState() => _QuoteDetailScreenState();
}

class _QuoteDetailScreenState extends State<QuoteDetailScreen> {
  late Future<Quote> _future;

  QuotesRepository get _repo => QuotesRepository(context.read<ApiClient>());

  @override
  void initState() {
    super.initState();
    _future = _repo.get(widget.quoteId);
  }

  Future<void> _refresh() async {
    setState(() => _future = _repo.get(widget.quoteId));
  }

  Future<void> _send() async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      await _repo.send(widget.quoteId);
      messenger.showSnackBar(
        const SnackBar(content: Text('Quote sent.')),
      );
      _refresh();
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Failed: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final fmt = DateFormat('yyyy-MM-dd');
    return Scaffold(
      appBar: AppBar(title: const Text('Quote')),
      body: FutureBuilder<Quote>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return Center(child: Text('Error: ${snap.error}'));
          }
          final q = snap.data!;
          return RefreshIndicator(
            onRefresh: _refresh,
            child: ListView(
              padding: const EdgeInsets.all(12),
              children: [
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          q.number,
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                        const SizedBox(height: 4),
                        Text(q.recipientName),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 8,
                          runSpacing: 4,
                          children: [
                            Chip(label: Text(q.statusDisplay)),
                            if (q.isExpired)
                              const Chip(
                                label: Text('Expired'),
                                backgroundColor: Color(0x33FF6B6B),
                              ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        if (q.validUntil != null)
                          Text('Valid until ${fmt.format(q.validUntil!)}'),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        const Text(
                          'Lines',
                          style: TextStyle(fontWeight: FontWeight.w600),
                        ),
                        const SizedBox(height: 8),
                        for (final ln in q.lines)
                          Padding(
                            padding: const EdgeInsets.symmetric(vertical: 4),
                            child: Row(
                              children: [
                                Expanded(child: Text(ln.description)),
                                Text(
                                  '${ln.quantity} × ${q.currency} ${ln.unitAmount}',
                                  style:
                                      const TextStyle(color: Colors.grey),
                                ),
                                const SizedBox(width: 12),
                                Text('${q.currency} ${ln.lineTotal}'),
                              ],
                            ),
                          ),
                        const Divider(),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Text('Total',
                                style: TextStyle(fontWeight: FontWeight.w600)),
                            Text(
                              '${q.currency} ${q.total}',
                              style: const TextStyle(
                                fontWeight: FontWeight.w700,
                                fontSize: 18,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                if (q.status == 'draft' || q.status == 'sent')
                  ElevatedButton.icon(
                    onPressed: _send,
                    icon: const Icon(Icons.send),
                    label: Text(q.status == 'draft' ? 'Send' : 'Re-send'),
                  ),
                if (q.convertedInvoiceId != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: OutlinedButton.icon(
                      onPressed: () => context.push(
                        '/billing/invoices/${q.convertedInvoiceId}',
                      ),
                      icon: const Icon(Icons.receipt_long),
                      label: const Text('View invoice'),
                    ),
                  ),
                if (q.notes.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Notes',
                            style: TextStyle(fontWeight: FontWeight.w600),
                          ),
                          const SizedBox(height: 6),
                          Text(q.notes),
                        ],
                      ),
                    ),
                  ),
                ],
              ],
            ),
          );
        },
      ),
    );
  }
}
