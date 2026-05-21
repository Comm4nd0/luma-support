import 'package:flutter/material.dart';

import '../../models/ticket.dart';
import '../../models/ticket_tag.dart';
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
    final subtitleChildren = <Widget>[
      Text('${ticket.clientName} · #${ticket.id}'),
      if (ticket.tags.isNotEmpty) ...[
        const SizedBox(height: 4),
        Wrap(
          spacing: 4,
          runSpacing: 4,
          children: [for (final tag in ticket.tags) _TagChip(tag: tag)],
        ),
      ],
    ];
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        onTap: onTap,
        title: Text(ticket.subject,
            maxLines: 1, overflow: TextOverflow.ellipsis),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: subtitleChildren,
        ),
        isThreeLine: ticket.tags.isNotEmpty,
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
            if (ticket.isPaused)
              const Text('PAUSED',
                  style: TextStyle(color: kMuted, fontSize: 11))
            else if (ticket.isBreached)
              const Text('BREACHED',
                  style: TextStyle(color: Colors.redAccent, fontSize: 11)),
          ],
        ),
      ),
    );
  }
}

class _TagChip extends StatelessWidget {
  const _TagChip({required this.tag});

  final TicketTag tag;

  @override
  Widget build(BuildContext context) {
    final color = parseTagColor(tag.color);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: color.withOpacity(0.18),
        border: Border.all(color: color.withOpacity(0.4)),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        tag.name,
        style: TextStyle(fontSize: 11, color: color, fontWeight: FontWeight.w600),
      ),
    );
  }
}

Color parseTagColor(String hex) {
  final cleaned = hex.replaceAll('#', '');
  final value = int.tryParse(cleaned, radix: 16) ?? 0x14b8a6;
  return Color(0xFF000000 | value);
}
