import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import 'package:provider/provider.dart';

import '../models/ticket.dart';
import '../repositories/tickets_repository.dart';
import '../services/api_client.dart';
import '../theme.dart';
import '../widgets/luma_icon.dart';
import 'widgets/luma_drawer.dart';

/// Kanban-style ticket board grouped by status — parity with the portal's
/// TicketBoardView. Closed tickets are excluded; each card carries a
/// "Move to…" menu that POSTs through the normal setStatus path, so the
/// audit log / SLA recompute / push fan-out all still fire.
class TicketBoardScreen extends StatefulWidget {
  const TicketBoardScreen({super.key});

  @override
  State<TicketBoardScreen> createState() => _TicketBoardScreenState();
}

class _TicketBoardScreenState extends State<TicketBoardScreen> {
  static const _lanes = <TicketStatus>[
    TicketStatus.newTicket,
    TicketStatus.assigned,
    TicketStatus.inProgress,
    TicketStatus.waiting,
    TicketStatus.resolved,
  ];

  late Future<List<Ticket>> _future;
  TicketsRepository get _repo => TicketsRepository(context.read<ApiClient>());

  @override
  void initState() {
    super.initState();
    _future = _repo.list();
  }

  Future<void> _refresh() async {
    setState(() => _future = _repo.list());
    await _future;
  }

  Future<void> _move(Ticket t, TicketStatus to) async {
    if (t.status == to) return;
    final messenger = ScaffoldMessenger.of(context);
    try {
      await _repo.setStatus(t.id, to);
      messenger.showSnackBar(
        SnackBar(content: Text('Moved #${t.id} to ${statusLabel(to)}.')),
      );
      await _refresh();
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Failed: $e')));
    }
  }

  List<Ticket> _laneTickets(List<Ticket> all, TicketStatus s) {
    final rows = all.where((t) => t.status == s).toList()
      ..sort((a, b) {
        final ad = a.slaDeadline;
        final bd = b.slaDeadline;
        if (ad == null && bd == null) return b.createdAt.compareTo(a.createdAt);
        if (ad == null) return 1;
        if (bd == null) return -1;
        return ad.compareTo(bd);
      });
    return rows;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Board'),
        actions: [
          IconButton(
            icon: const LumaIcon(PhosphorIconsDuotone.arrowsClockwise),
            onPressed: _refresh,
          ),
        ],
      ),
      drawer: const LumaDrawer(),
      body: FutureBuilder<List<Ticket>>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return Center(child: Text('Error: ${snap.error}'));
          }
          final all = snap.data!
              .where((t) => t.status != TicketStatus.closed)
              .toList();
          return RefreshIndicator(
            onRefresh: _refresh,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.all(8),
              children: [
                for (final lane in _lanes)
                  _Lane(
                    status: lane,
                    tickets: _laneTickets(all, lane),
                    onMove: _move,
                  ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _Lane extends StatelessWidget {
  const _Lane({
    required this.status,
    required this.tickets,
    required this.onMove,
  });

  final TicketStatus status;
  final List<Ticket> tickets;
  final void Function(Ticket, TicketStatus) onMove;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 280,
      margin: const EdgeInsets.symmetric(horizontal: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(4, 4, 4, 8),
            child: Row(
              children: [
                Text(
                  statusLabel(status),
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
                const SizedBox(width: 6),
                Text('${tickets.length}',
                    style: const TextStyle(color: kMuted)),
              ],
            ),
          ),
          Expanded(
            child: tickets.isEmpty
                ? const Padding(
                    padding: EdgeInsets.all(12),
                    child: Text('—', style: TextStyle(color: kMuted)),
                  )
                : ListView(
                    children: [
                      for (final t in tickets)
                        _BoardCard(ticket: t, onMove: onMove),
                    ],
                  ),
          ),
        ],
      ),
    );
  }
}

class _BoardCard extends StatelessWidget {
  const _BoardCard({required this.ticket, required this.onMove});

  final Ticket ticket;
  final void Function(Ticket, TicketStatus) onMove;

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
    final colour = _priorityColor(ticket.priority);
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: InkWell(
        onTap: () => context.push('/tickets/${ticket.id}'),
        child: Padding(
          padding: const EdgeInsets.all(10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 8,
                    height: 8,
                    decoration:
                        BoxDecoration(color: colour, shape: BoxShape.circle),
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      ticket.subject,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontWeight: FontWeight.w600),
                    ),
                  ),
                  PopupMenuButton<TicketStatus>(
                    icon: const Icon(Icons.more_vert, size: 18),
                    tooltip: 'Move to…',
                    onSelected: (to) => onMove(ticket, to),
                    itemBuilder: (_) => [
                      for (final s in TicketStatus.values)
                        if (s != ticket.status)
                          PopupMenuItem(
                            value: s,
                            child: Text('Move to ${statusLabel(s)}'),
                          ),
                    ],
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Text('${ticket.clientName} · #${ticket.id}',
                  style: const TextStyle(fontSize: 12, color: kMuted)),
              if (ticket.isPaused)
                const Text('PAUSED',
                    style: TextStyle(fontSize: 11, color: kMuted))
              else if (ticket.isBreached)
                const Text('BREACHED',
                    style: TextStyle(fontSize: 11, color: Colors.redAccent)),
            ],
          ),
        ),
      ),
    );
  }
}
