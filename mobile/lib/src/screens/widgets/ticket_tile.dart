import 'package:flutter/material.dart';

import '../../models/ticket.dart';
import '../../theme.dart';

/// Compact list tile used on dashboards and the ticket list. Pulled into
/// its own file so styling stays consistent across screens.
class TicketTile extends StatelessWidget {
  const TicketTile({super.key, required this.ticket, this.onTap});

  final Ticket ticket;
  final VoidCallback? onTap;

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
      child: ListTile(
        onTap: onTap,
        title: Text(ticket.subject,
            maxLines: 1, overflow: TextOverflow.ellipsis),
        subtitle: Text('${ticket.clientName} · #${ticket.id}'),
        leading: CircleAvatar(
          backgroundColor: colour.withOpacity(0.18),
          child: Text(
            ticket.priority.name.substring(0, 1).toUpperCase(),
            style: TextStyle(color: colour),
          ),
        ),
        trailing: Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(ticket.status.name, style: const TextStyle(fontSize: 12)),
            if (ticket.isBreached)
              const Text('BREACHED',
                  style: TextStyle(color: Colors.redAccent, fontSize: 11)),
          ],
        ),
      ),
    );
  }
}
