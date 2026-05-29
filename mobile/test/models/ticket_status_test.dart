import 'package:flutter_test/flutter_test.dart';

import 'package:luma_support_mobile/src/models/ticket.dart';

void main() {
  group('ticket status helpers', () {
    test('statusLabel matches the portal Ticket.Status choices', () {
      expect(statusLabel(TicketStatus.newTicket), 'New');
      expect(statusLabel(TicketStatus.assigned), 'Assigned');
      expect(statusLabel(TicketStatus.inProgress), 'In progress');
      expect(statusLabel(TicketStatus.waiting), 'Waiting on client');
      expect(statusLabel(TicketStatus.resolved), 'Resolved');
      expect(statusLabel(TicketStatus.closed), 'Closed');
    });

    test('statusToWire / statusFromString round-trip for every status', () {
      for (final s in TicketStatus.values) {
        expect(statusFromString(statusToWire(s)), s);
      }
    });
  });
}
