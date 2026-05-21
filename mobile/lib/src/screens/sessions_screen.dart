import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../repositories/sessions_repository.dart';
import '../services/api_client.dart';

/// Active JWT refresh-token sessions for the current user, with
/// per-session and revoke-all controls.
class SessionsScreen extends StatefulWidget {
  const SessionsScreen({super.key});

  @override
  State<SessionsScreen> createState() => _SessionsScreenState();
}

class _SessionsScreenState extends State<SessionsScreen> {
  late Future<List<SessionEntry>> _future;
  SessionsRepository get _repo =>
      SessionsRepository(context.read<ApiClient>());

  @override
  void initState() {
    super.initState();
    _future = _repo.list();
  }

  Future<void> _refresh() async {
    setState(() => _future = _repo.list());
  }

  Future<void> _revoke(SessionEntry s) async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      await _repo.revoke(s.id);
      messenger
          .showSnackBar(const SnackBar(content: Text('Session revoked.')));
      if (mounted) _refresh();
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Failed: $e')));
    }
  }

  Future<void> _revokeAll() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Sign out everywhere?'),
        content: const Text(
          'This will revoke every refresh token tied to your account — '
          'including the one this app is using. You will be signed out on '
          'every device, including this one.',
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Revoke all'),
          ),
        ],
      ),
    );
    if (confirm != true) return;
    final messenger = ScaffoldMessenger.of(context);
    try {
      final n = await _repo.revokeAll();
      messenger.showSnackBar(SnackBar(content: Text('Revoked $n sessions.')));
      if (mounted) _refresh();
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Failed: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Active sessions'),
        actions: [
          TextButton(
            onPressed: _revokeAll,
            child: const Text('Revoke all',
                style: TextStyle(color: Colors.redAccent)),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<List<SessionEntry>>(
          future: _future,
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snap.hasError) {
              return Center(child: Text('Error: ${snap.error}'));
            }
            final sessions = snap.data ?? const <SessionEntry>[];
            if (sessions.isEmpty) {
              return const Center(child: Text('No active sessions.'));
            }
            return ListView.builder(
              padding: const EdgeInsets.all(12),
              itemCount: sessions.length,
              itemBuilder: (_, i) {
                final s = sessions[i];
                return Card(
                  margin: const EdgeInsets.only(bottom: 8),
                  child: ListTile(
                    leading: const Icon(Icons.devices_outlined),
                    title: Text(
                      s.createdAt == null
                          ? 'Session #${s.id}'
                          : 'Issued ${DateFormat.yMd().add_Hm().format(s.createdAt!.toLocal())}',
                    ),
                    subtitle: Text(
                      s.expiresAt == null
                          ? ''
                          : 'Expires ${DateFormat.yMd().format(s.expiresAt!.toLocal())}',
                    ),
                    trailing: IconButton(
                      tooltip: 'Revoke',
                      icon:
                          const Icon(Icons.logout, color: Colors.redAccent),
                      onPressed: () => _revoke(s),
                    ),
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
