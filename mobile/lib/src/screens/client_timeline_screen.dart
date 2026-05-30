import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models/timeline_event.dart';
import '../repositories/clients_repository.dart';
import '../services/api_client.dart';
import '../theme.dart';

/// Unified per-client communication log — tickets, notes, quotes, invoices,
/// lead activity. Parity with the portal ClientTimelineView.
class ClientTimelineScreen extends StatefulWidget {
  const ClientTimelineScreen({super.key, required this.clientId});

  final int clientId;

  @override
  State<ClientTimelineScreen> createState() => _ClientTimelineScreenState();
}

class _ClientTimelineScreenState extends State<ClientTimelineScreen> {
  late Future<List<TimelineEvent>> _future;
  ClientsRepository get _repo => ClientsRepository(context.read<ApiClient>());

  @override
  void initState() {
    super.initState();
    _future = _repo.timeline(widget.clientId);
  }

  Future<void> _refresh() async {
    setState(() => _future = _repo.timeline(widget.clientId));
    await _future;
  }

  /// Map a web event URL (e.g. "/tickets/42/") to the mobile route, or null
  /// when there's nothing to open (e.g. lead activity).
  String? _route(TimelineEvent e) {
    if (e.url.isEmpty) return null;
    return e.url.endsWith('/') ? e.url.substring(0, e.url.length - 1) : e.url;
  }

  IconData _icon(String kind) {
    switch (kind) {
      case 'ticket':
        return Icons.confirmation_number_outlined;
      case 'ticket_note':
        return Icons.sticky_note_2_outlined;
      case 'quote':
        return Icons.request_quote_outlined;
      case 'invoice':
        return Icons.receipt_long_outlined;
      case 'lead_activity':
        return Icons.campaign_outlined;
      default:
        return Icons.circle_outlined;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Timeline')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<List<TimelineEvent>>(
          future: _future,
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snap.hasError) {
              return Center(child: Text('Error: ${snap.error}'));
            }
            final events = snap.data!;
            if (events.isEmpty) {
              return ListView(
                children: const [
                  Padding(
                    padding: EdgeInsets.all(32),
                    child: Center(
                      child: Text('No activity yet.',
                          style: TextStyle(color: kMuted)),
                    ),
                  ),
                ],
              );
            }
            return ListView.builder(
              padding: const EdgeInsets.all(12),
              itemCount: events.length,
              itemBuilder: (context, i) {
                final e = events[i];
                final route = _route(e);
                return Card(
                  margin: const EdgeInsets.only(bottom: 8),
                  child: ListTile(
                    leading: Icon(_icon(e.kind)),
                    title: Text(e.title,
                        maxLines: 2, overflow: TextOverflow.ellipsis),
                    subtitle: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        if (e.body.isNotEmpty)
                          Text(e.body,
                              maxLines: 3, overflow: TextOverflow.ellipsis),
                        if (e.occurredAt != null)
                          Text(
                            DateFormat.yMMMd().add_jm().format(
                                  e.occurredAt!.toLocal(),
                                ),
                            style: const TextStyle(
                                fontSize: 11, color: kMuted),
                          ),
                      ],
                    ),
                    trailing: route == null
                        ? null
                        : const Icon(Icons.chevron_right),
                    onTap: route == null ? null : () => context.push(route),
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
