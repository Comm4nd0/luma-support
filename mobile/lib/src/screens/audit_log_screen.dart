import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models/audit_log.dart';
import '../repositories/audit_repository.dart';
import '../services/api_client.dart';

/// Admin-only audit feed. Parity with the portal's /audit/ page.
class AuditLogScreen extends StatefulWidget {
  const AuditLogScreen({super.key});

  @override
  State<AuditLogScreen> createState() => _AuditLogScreenState();
}

class _AuditLogScreenState extends State<AuditLogScreen> {
  late Future<List<AuditLogEntry>> _future;
  final _filter = TextEditingController();

  AuditRepository get _repo => AuditRepository(context.read<ApiClient>());

  @override
  void initState() {
    super.initState();
    _future = _repo.list();
  }

  void _applyFilter() {
    setState(() => _future = _repo.list(action: _filter.text.trim()));
  }

  Future<void> _refresh() async {
    setState(() => _future = _repo.list(action: _filter.text.trim()));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Audit log')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: TextField(
              controller: _filter,
              decoration: InputDecoration(
                hintText: 'Filter by action (e.g. xero)',
                prefixIcon: const Icon(Icons.filter_alt_outlined),
                suffixIcon: IconButton(
                  icon: const Icon(Icons.search),
                  onPressed: _applyFilter,
                ),
              ),
              onSubmitted: (_) => _applyFilter(),
            ),
          ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: _refresh,
              child: FutureBuilder<List<AuditLogEntry>>(
                future: _future,
                builder: (context, snap) {
                  if (snap.connectionState != ConnectionState.done) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  if (snap.hasError) {
                    return Center(child: Text('Error: ${snap.error}'));
                  }
                  final items = snap.data ?? const <AuditLogEntry>[];
                  if (items.isEmpty) {
                    return const Center(child: Text('No audit entries.'));
                  }
                  return ListView.builder(
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    itemCount: items.length,
                    itemBuilder: (_, i) {
                      final e = items[i];
                      return Card(
                        margin: const EdgeInsets.only(bottom: 8),
                        child: ListTile(
                          title: Text(
                            e.action,
                            style: const TextStyle(
                              fontFamily: 'monospace',
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          subtitle: Text(
                            '${e.actorEmail ?? "system"} · ${DateFormat.yMd().add_Hms().format(e.createdAt.toLocal())}'
                            '${e.targetRepr.isEmpty ? "" : "\n${e.targetRepr}"}',
                          ),
                          isThreeLine: e.targetRepr.isNotEmpty,
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
