import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../models/ticket.dart';
import '../models/ticket_tag.dart';
import '../repositories/tickets_repository.dart';
import '../services/api_client.dart';
import '../services/current_user.dart';
import 'widgets/luma_drawer.dart';
import 'widgets/ticket_tile.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../../src/widgets/luma_icon.dart';

class TicketListScreen extends StatefulWidget {
  const TicketListScreen({super.key});

  @override
  State<TicketListScreen> createState() => _TicketListScreenState();
}

class _TicketListScreenState extends State<TicketListScreen> {
  late Future<List<Ticket>> _future;
  Future<List<TicketTag>>? _tagsFuture;
  String? _activeTagSlug;

  TicketsRepository get _repo =>
      TicketsRepository(context.read<ApiClient>());

  @override
  void initState() {
    super.initState();
    _future = _load();
    _tagsFuture = _repo.listTags();
  }

  Future<List<Ticket>> _load() => _repo.list(tagSlug: _activeTagSlug);

  Future<void> _refresh() async {
    setState(() {
      _future = _load();
    });
  }

  void _setTag(String? slug) {
    setState(() {
      _activeTagSlug = slug;
      _future = _load();
    });
  }

  @override
  Widget build(BuildContext context) {
    final isStaff = context.watch<CurrentUser>().isStaff;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Tickets'),
        actions: [
          IconButton(
            icon: const LumaIcon(PhosphorIconsDuotone.arrowsClockwise),
            onPressed: _refresh,
          ),
        ],
      ),
      drawer: isStaff ? const LumaDrawer() : null,
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () async {
          await context.push('/tickets/new');
          if (mounted) _refresh();
        },
        icon: const LumaIcon(PhosphorIconsDuotone.plus),
        label: const Text('New ticket'),
      ),
      body: Column(
        children: [
          FutureBuilder<List<TicketTag>>(
            future: _tagsFuture,
            builder: (context, snap) {
              final tags = snap.data ?? const <TicketTag>[];
              if (tags.isEmpty) return const SizedBox.shrink();
              return SizedBox(
                height: 44,
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  children: [
                    Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: FilterChip(
                        label: const Text('All'),
                        selected: _activeTagSlug == null,
                        onSelected: (_) => _setTag(null),
                      ),
                    ),
                    for (final tag in tags)
                      Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: FilterChip(
                          label: Text(tag.name),
                          selected: _activeTagSlug == tag.slug,
                          onSelected: (_) => _setTag(tag.slug),
                          selectedColor:
                              parseTagColor(tag.color).withOpacity(0.25),
                          checkmarkColor: parseTagColor(tag.color),
                        ),
                      ),
                  ],
                ),
              );
            },
          ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: _refresh,
              child: FutureBuilder<List<Ticket>>(
                future: _future,
                builder: (context, snapshot) {
                  if (snapshot.connectionState != ConnectionState.done) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  if (snapshot.hasError) {
                    return Center(child: Text('Error: ${snapshot.error}'));
                  }
                  final items = snapshot.data ?? const <Ticket>[];
                  if (items.isEmpty) {
                    return const Center(child: Text('No tickets match.'));
                  }
                  return ListView.builder(
                    padding: const EdgeInsets.all(12),
                    itemCount: items.length,
                    itemBuilder: (_, i) {
                      final t = items[i];
                      return TicketTile(
                        ticket: t,
                        onTap: () async {
                          await context.push('/tickets/${t.id}');
                          if (mounted) _refresh();
                        },
                      );
                    },
                  );
                },
              ),
            ),
          ),
        ],
      ),
    );
  }
}
