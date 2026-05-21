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

class _BulkChoice {
  const _BulkChoice({required this.action, this.value});
  final String action;
  final Object? value;
}

const _statusOptions = [
  'new',
  'assigned',
  'in_progress',
  'waiting',
  'resolved',
  'closed',
];
const _priorityOptions = ['critical', 'high', 'medium', 'low'];

class _BulkActionSheet extends StatefulWidget {
  const _BulkActionSheet({required this.tags});
  final List<TicketTag> tags;

  @override
  State<_BulkActionSheet> createState() => _BulkActionSheetState();
}

class _BulkActionSheetState extends State<_BulkActionSheet> {
  String _action = 'status';
  String? _value;

  List<String> _valuesFor(String action) {
    switch (action) {
      case 'status':
        return _statusOptions;
      case 'priority':
        return _priorityOptions;
      case 'add_tag':
      case 'remove_tag':
        return widget.tags.map((t) => t.slug).toList();
    }
    return const [];
  }

  String _labelFor(String action, String value) {
    if (action == 'add_tag' || action == 'remove_tag') {
      final t = widget.tags.firstWhere(
        (x) => x.slug == value,
        orElse: () => TicketTag(id: 0, name: value, slug: value, color: '#14b8a6'),
      );
      return t.name;
    }
    return value.replaceAll('_', ' ');
  }

  @override
  Widget build(BuildContext context) {
    final values = _valuesFor(_action);
    if (_value != null && !values.contains(_value)) _value = null;
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text('Bulk action',
                style: TextStyle(fontWeight: FontWeight.w600)),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              value: _action,
              decoration: const InputDecoration(labelText: 'Action'),
              items: const [
                DropdownMenuItem(value: 'status', child: Text('Set status')),
                DropdownMenuItem(value: 'priority', child: Text('Set priority')),
                DropdownMenuItem(value: 'add_tag', child: Text('Add tag')),
                DropdownMenuItem(value: 'remove_tag', child: Text('Remove tag')),
              ],
              onChanged: (v) => setState(() {
                _action = v ?? 'status';
                _value = null;
              }),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              value: _value,
              decoration: const InputDecoration(labelText: 'Value'),
              items: [
                for (final v in values)
                  DropdownMenuItem(value: v, child: Text(_labelFor(_action, v))),
              ],
              onChanged: (v) => setState(() => _value = v),
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Cancel'),
                ),
                const SizedBox(width: 8),
                ElevatedButton(
                  onPressed: _value == null
                      ? null
                      : () => Navigator.pop(
                            context,
                            _BulkChoice(action: _action, value: _value),
                          ),
                  child: const Text('Apply'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class TicketListScreen extends StatefulWidget {
  const TicketListScreen({super.key});

  @override
  State<TicketListScreen> createState() => _TicketListScreenState();
}

class _TicketListScreenState extends State<TicketListScreen> {
  late Future<List<Ticket>> _future;
  Future<List<TicketTag>>? _tagsFuture;
  String? _activeTagSlug;
  final Set<int> _selected = {};

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

  bool get _selectionMode => _selected.isNotEmpty;

  void _toggleSelected(int id) {
    setState(() {
      if (_selected.contains(id)) {
        _selected.remove(id);
      } else {
        _selected.add(id);
      }
    });
  }

  void _clearSelection() {
    setState(() => _selected.clear());
  }

  Future<void> _runBulk(BuildContext context) async {
    final tags = await _repo.listTags();
    if (!mounted) return;
    final result = await showModalBottomSheet<_BulkChoice>(
      context: context,
      builder: (_) => _BulkActionSheet(tags: tags),
    );
    if (result == null) return;
    final messenger = ScaffoldMessenger.of(context);
    try {
      final touched = await _repo.bulk(
        ids: _selected.toList(),
        action: result.action,
        value: result.value,
      );
      messenger.showSnackBar(
        SnackBar(content: Text('Applied to $touched ticket(s).')),
      );
      _clearSelection();
      _refresh();
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Bulk failed: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final isStaff = context.watch<CurrentUser>().isStaff;
    return Scaffold(
      appBar: _selectionMode
          ? AppBar(
              leading: IconButton(
                icon: const Icon(Icons.close),
                onPressed: _clearSelection,
              ),
              title: Text('${_selected.length} selected'),
              actions: [
                IconButton(
                  icon: const Icon(Icons.playlist_play),
                  tooltip: 'Bulk action',
                  onPressed: () => _runBulk(context),
                ),
              ],
            )
          : AppBar(
              title: const Text('Tickets'),
              actions: [
                IconButton(
                  icon: const LumaIcon(PhosphorIconsDuotone.arrowsClockwise),
                  onPressed: _refresh,
                ),
              ],
            ),
      drawer: isStaff && !_selectionMode ? const LumaDrawer() : null,
      floatingActionButton: _selectionMode
          ? null
          : FloatingActionButton.extended(
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
                      final selected = _selected.contains(t.id);
                      return Container(
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(12),
                          color: selected ? Colors.teal.withOpacity(0.15) : null,
                        ),
                        child: TicketTile(
                          ticket: t,
                          onTap: () async {
                            if (_selectionMode) {
                              _toggleSelected(t.id);
                              return;
                            }
                            await context.push('/tickets/${t.id}');
                            if (mounted) _refresh();
                          },
                          onLongPress: isStaff ? () => _toggleSelected(t.id) : null,
                        ),
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
