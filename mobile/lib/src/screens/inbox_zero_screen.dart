import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../models/ticket.dart';
import '../repositories/tickets_repository.dart';
import '../services/api_client.dart';
import '../services/current_user.dart';

/// "Clear my queue" — Claude proposes one action per open ticket
/// assigned to me; I swipe through and approve / skip.
///
/// Approval rules:
/// - ``close``  → POST status=closed on the ticket (uses the existing
///   status endpoint which writes the audit trail + push notification).
/// - ``reply``  → just opens the ticket (the engineer writes the reply
///   themselves).
/// - ``ask``    → opens the ticket with the note compose ready (same
///   path as reply for now).
/// - ``defer``  → no-op locally; the AI will surface it again
///   tomorrow if the situation hasn't changed.
class InboxZeroScreen extends StatefulWidget {
  const InboxZeroScreen({super.key});

  @override
  State<InboxZeroScreen> createState() => _InboxZeroScreenState();
}

class _InboxZeroScreenState extends State<InboxZeroScreen> {
  late Future<List<Map<String, dynamic>>> _future;
  TicketsRepository get _repo =>
      TicketsRepository(context.read<ApiClient>());

  @override
  void initState() {
    super.initState();
    _future = _repo.inboxZero();
  }

  Future<void> _refresh() async {
    setState(() => _future = _repo.inboxZero());
  }

  Future<void> _approve(Map<String, dynamic> suggestion) async {
    final ticketId = (suggestion['ticket_id'] as num?)?.toInt();
    final action = suggestion['action'] as String?;
    if (ticketId == null || action == null) return;
    final messenger = ScaffoldMessenger.of(context);
    try {
      if (action == 'close') {
        await _repo.setStatus(ticketId, TicketStatus.closed);
        messenger.showSnackBar(
          SnackBar(content: Text('Ticket #$ticketId closed.')),
        );
        if (!mounted) return;
        setState(() {
          // Optimistic local removal so the list reflects the action
          // even before the next AI fetch.
          _future = _future.then(
            (rows) => rows.where((r) => r['ticket_id'] != ticketId).toList(),
          );
        });
      } else {
        // reply / ask / defer: jump to the ticket so the engineer can
        // act. Defer still opens so they can sanity-check before
        // moving on.
        if (!mounted) return;
        await context.push('/tickets/$ticketId');
        _refresh();
      }
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Failed: $e')));
    }
  }

  void _skip(Map<String, dynamic> suggestion) {
    final ticketId = suggestion['ticket_id'];
    setState(() {
      _future = _future.then(
        (rows) => rows.where((r) => r['ticket_id'] != ticketId).toList(),
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    final isStaff = context.watch<CurrentUser>().isStaff;
    if (!isStaff) {
      return Scaffold(
        appBar: AppBar(title: const Text('Clear queue')),
        body: const Center(child: Text('Staff only.')),
      );
    }
    return Scaffold(
      appBar: AppBar(
        title: const Text('Clear queue'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Re-run AI triage',
            onPressed: _refresh,
          ),
        ],
      ),
      body: FutureBuilder<List<Map<String, dynamic>>>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return Center(child: Text('Error: ${snap.error}'));
          }
          final rows = snap.data ?? const <Map<String, dynamic>>[];
          if (rows.isEmpty) {
            return const _EmptyHint(
              'No suggestions — either the queue is clear or '
              'ANTHROPIC_API_KEY isn\'t set on the server.',
            );
          }
          return ListView.separated(
            padding: const EdgeInsets.all(12),
            itemCount: rows.length,
            separatorBuilder: (_, __) => const SizedBox(height: 8),
            itemBuilder: (_, i) => _SuggestionCard(
              row: rows[i],
              onApprove: () => _approve(rows[i]),
              onSkip: () => _skip(rows[i]),
            ),
          );
        },
      ),
    );
  }
}

class _SuggestionCard extends StatelessWidget {
  const _SuggestionCard({
    required this.row,
    required this.onApprove,
    required this.onSkip,
  });

  final Map<String, dynamic> row;
  final VoidCallback onApprove;
  final VoidCallback onSkip;

  Color _actionColor(BuildContext context, String action) {
    switch (action) {
      case 'close':
        return Colors.tealAccent;
      case 'reply':
        return Theme.of(context).colorScheme.primary;
      case 'ask':
        return Colors.amber;
      case 'defer':
      default:
        return Colors.white54;
    }
  }

  @override
  Widget build(BuildContext context) {
    final action = (row['action'] as String?) ?? 'defer';
    final ticketId = row['ticket_id']?.toString() ?? '?';
    final reason = (row['reason'] as String?) ?? '';
    final actionColor = _actionColor(context, action);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: actionColor.withOpacity(0.18),
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    action.toUpperCase(),
                    style: TextStyle(
                      color: actionColor,
                      fontWeight: FontWeight.w700,
                      fontSize: 11,
                    ),
                  ),
                ),
                const Spacer(),
                Text('#$ticketId',
                    style: const TextStyle(fontWeight: FontWeight.w600)),
              ],
            ),
            const SizedBox(height: 8),
            Text(reason, style: const TextStyle(height: 1.4)),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton(onPressed: onSkip, child: const Text('Skip')),
                const SizedBox(width: 8),
                ElevatedButton(
                  onPressed: onApprove,
                  child: Text(action == 'close' ? 'Approve & close' : 'Open ticket'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _EmptyHint extends StatelessWidget {
  const _EmptyHint(this.message);
  final String message;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(
            message,
            textAlign: TextAlign.center,
            style: const TextStyle(color: Colors.white60),
          ),
        ),
      );
}
