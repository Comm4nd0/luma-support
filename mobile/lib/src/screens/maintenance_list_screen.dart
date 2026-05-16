import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models/maintenance_schedule.dart';
import '../repositories/maintenance_repository.dart';
import '../services/api_client.dart';

/// Staff-only list of recurring maintenance schedules.
/// Parity with the portal's /schedules/ page.
class MaintenanceListScreen extends StatefulWidget {
  const MaintenanceListScreen({super.key});

  @override
  State<MaintenanceListScreen> createState() => _MaintenanceListScreenState();
}

class _MaintenanceListScreenState extends State<MaintenanceListScreen> {
  late Future<List<MaintenanceSchedule>> _future;

  MaintenanceRepository get _repo =>
      MaintenanceRepository(context.read<ApiClient>());

  @override
  void initState() {
    super.initState();
    _future = _repo.list();
  }

  Future<void> _refresh() async {
    setState(() => _future = _repo.list());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Maintenance schedules')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<List<MaintenanceSchedule>>(
          future: _future,
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snap.hasError) {
              return Center(child: Text('Error: ${snap.error}'));
            }
            final items = snap.data ?? const <MaintenanceSchedule>[];
            if (items.isEmpty) {
              return const Center(
                child: Padding(
                  padding: EdgeInsets.all(24),
                  child: Text(
                    'No maintenance schedules yet. Create one from the web '
                    'portal to start auto-generating tickets for recurring '
                    'work.',
                    textAlign: TextAlign.center,
                  ),
                ),
              );
            }
            return ListView.builder(
              padding: const EdgeInsets.all(12),
              itemCount: items.length,
              itemBuilder: (_, i) {
                final s = items[i];
                return Card(
                  margin: const EdgeInsets.only(bottom: 8),
                  child: ListTile(
                    leading: Icon(
                      s.active ? Icons.event_repeat : Icons.event_busy,
                      color: s.active ? Colors.teal : Colors.grey,
                    ),
                    title: Text(s.templateSubject),
                    subtitle: Text(
                      '${s.clientName}${s.systemName != null && s.systemName!.isNotEmpty ? " · ${s.systemName}" : ""}\n'
                      '${cadenceLabel(s.cadence)} · next ${s.nextRunAt == null ? "—" : DateFormat.yMMMd().format(s.nextRunAt!)}',
                    ),
                    isThreeLine: true,
                    trailing: !s.active
                        ? const Chip(label: Text('Paused'))
                        : null,
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
