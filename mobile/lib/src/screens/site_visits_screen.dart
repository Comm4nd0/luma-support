import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import 'package:provider/provider.dart';

import '../models/site_visit.dart';
import '../repositories/site_visits_repository.dart';
import '../services/api_client.dart';
import '../services/current_user.dart';
import 'widgets/luma_drawer.dart';
import '../../src/widgets/luma_icon.dart';

/// Engineer / admin: open visits at the top (with a big "End" button),
/// then recently-closed visits below. Tap an open visit to open the
/// end-visit dialog with an optional ticket selector.
class SiteVisitsScreen extends StatefulWidget {
  const SiteVisitsScreen({super.key});

  @override
  State<SiteVisitsScreen> createState() => _SiteVisitsScreenState();
}

class _SiteVisitsScreenState extends State<SiteVisitsScreen> {
  late Future<List<SiteVisit>> _future;

  SiteVisitsRepository get _repo =>
      SiteVisitsRepository(context.read<ApiClient>());

  @override
  void initState() {
    super.initState();
    _future = _repo.list();
  }

  Future<void> _refresh() async {
    setState(() {
      _future = _repo.list();
    });
  }

  Future<void> _endVisit(SiteVisit visit) async {
    final notesController = TextEditingController();
    final ticketIdController = TextEditingController();
    final messenger = ScaffoldMessenger.of(context);
    final result = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('End visit'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: ticketIdController,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                labelText: 'Roll into ticket # (optional)',
              ),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: notesController,
              maxLines: 3,
              decoration: const InputDecoration(labelText: 'Notes (optional)'),
            ),
          ],
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('End'),
          ),
        ],
      ),
    );
    if (result != true) return;
    final ticketId = int.tryParse(ticketIdController.text.trim());
    try {
      await _repo.end(
        visit.id,
        ticketId: ticketId,
        notes: notesController.text.trim().isEmpty
            ? null
            : notesController.text.trim(),
      );
      messenger.showSnackBar(const SnackBar(content: Text('Visit ended.')));
      if (mounted) _refresh();
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Failed: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final isStaff = context.watch<CurrentUser>().isStaff;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Site visits'),
        actions: [
          IconButton(
            icon: const LumaIcon(PhosphorIconsDuotone.arrowsClockwise),
            onPressed: _refresh,
          ),
        ],
      ),
      drawer: isStaff ? const LumaDrawer() : null,
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<List<SiteVisit>>(
          future: _future,
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snap.hasError) {
              return Center(child: Text('Error: ${snap.error}'));
            }
            final visits = snap.data ?? const <SiteVisit>[];
            final open = visits.where((v) => v.isOpen).toList();
            final closed = visits.where((v) => !v.isOpen).toList();
            if (visits.isEmpty) {
              return const Center(child: Text('No site visits yet.'));
            }
            return ListView(
              padding: const EdgeInsets.all(12),
              children: [
                if (open.isNotEmpty) ...[
                  const _SectionLabel('Open'),
                  for (final v in open)
                    _OpenVisitCard(visit: v, onEnd: () => _endVisit(v)),
                  const SizedBox(height: 12),
                ],
                if (closed.isNotEmpty) const _SectionLabel('Recent'),
                for (final v in closed) _ClosedVisitCard(visit: v),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel(this.label);
  final String label;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 6),
      child: Text(
        label.toUpperCase(),
        style: TextStyle(
          fontSize: 11,
          letterSpacing: 1.2,
          fontWeight: FontWeight.w600,
          color: Theme.of(context).colorScheme.onSurface.withOpacity(0.6),
        ),
      ),
    );
  }
}

class _OpenVisitCard extends StatelessWidget {
  const _OpenVisitCard({required this.visit, required this.onEnd});

  final SiteVisit visit;
  final VoidCallback onEnd;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        leading: const Icon(Icons.location_on_outlined, color: Colors.tealAccent),
        title: Text('Client #${visit.clientId}'),
        subtitle: Text(
          'Started ${visit.startedAt != null ? DateFormat.Hm().format(visit.startedAt!.toLocal()) : "—"}'
          '${visit.userEmail != null ? " · ${visit.userEmail}" : ""}',
        ),
        trailing: ElevatedButton(
          onPressed: onEnd,
          child: const Text('End'),
        ),
      ),
    );
  }
}

class _ClosedVisitCard extends StatelessWidget {
  const _ClosedVisitCard({required this.visit});

  final SiteVisit visit;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        leading: const Icon(Icons.flag_circle_outlined),
        title: Text('Client #${visit.clientId}'),
        subtitle: Text(
          '${visit.durationMinutes ?? 0} min'
          '${visit.startedAt != null ? " · ${DateFormat.yMd().add_Hm().format(visit.startedAt!.toLocal())}" : ""}',
        ),
        trailing: visit.timeEntryId != null
            ? const Icon(Icons.check_circle_outline, color: Colors.tealAccent)
            : null,
      ),
    );
  }
}
