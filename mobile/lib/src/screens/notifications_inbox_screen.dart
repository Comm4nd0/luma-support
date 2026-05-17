import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models/app_notification.dart';
import '../repositories/notifications_repository.dart';
import '../services/api_client.dart';
import '../services/current_user.dart';
import 'widgets/luma_drawer.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../../src/widgets/luma_icon.dart';

class NotificationsInboxScreen extends StatefulWidget {
  const NotificationsInboxScreen({super.key});

  @override
  State<NotificationsInboxScreen> createState() =>
      _NotificationsInboxScreenState();
}

class _NotificationsInboxScreenState extends State<NotificationsInboxScreen> {
  late Future<List<AppNotification>> _future;

  NotificationsRepository get _repo =>
      NotificationsRepository(context.read<ApiClient>());

  @override
  void initState() {
    super.initState();
    _future = _repo.list();
  }

  Future<void> _refresh() async {
    setState(() => _future = _repo.list());
  }

  Future<void> _markAllRead() async {
    await _repo.markAllRead();
    await _refresh();
  }

  Future<void> _open(AppNotification n) async {
    if (!n.read) {
      try {
        await _repo.markRead(n.id);
      } catch (_) {}
    }
    if (n.relatedTicketId != null && mounted) {
      context.push('/tickets/${n.relatedTicketId}');
    }
  }

  @override
  Widget build(BuildContext context) {
    final isStaff = context.watch<CurrentUser>().isStaff;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Alerts'),
        actions: [
          IconButton(
            tooltip: 'Mark all read',
            icon: const LumaIcon(PhosphorIconsDuotone.checks),
            onPressed: _markAllRead,
          ),
        ],
      ),
      drawer: isStaff ? const LumaDrawer() : null,
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<List<AppNotification>>(
          future: _future,
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snap.hasError) {
              return Center(child: Text('Error: ${snap.error}'));
            }
            final items = snap.data ?? const <AppNotification>[];
            if (items.isEmpty) {
              return const Center(child: Text('No notifications.'));
            }
            final fmt = DateFormat.MMMd().add_jm();
            return ListView.builder(
              padding: const EdgeInsets.all(12),
              itemCount: items.length,
              itemBuilder: (_, i) {
                final n = items[i];
                return Card(
                  margin: const EdgeInsets.only(bottom: 8),
                  child: ListTile(
                    onTap: () => _open(n),
                    leading: CircleAvatar(
                      backgroundColor: n.read
                          ? Colors.grey.withOpacity(0.18)
                          : Theme.of(context)
                              .colorScheme
                              .primary
                              .withOpacity(0.18),
                      child: Icon(
                        _iconFor(n.type),
                        color: n.read
                            ? Colors.grey
                            : Theme.of(context).colorScheme.primary,
                      ),
                    ),
                    title: Text(
                      n.title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                          fontWeight:
                              n.read ? FontWeight.w400 : FontWeight.w600),
                    ),
                    subtitle: Text(
                      '${n.body.split('\n').first} · ${fmt.format(n.createdAt.toLocal())}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
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

  IconData _iconFor(String type) {
    switch (type) {
      case 'sla_warning':
        return PhosphorIconsDuotone.warning;
      case 'new_ticket':
        return PhosphorIconsDuotone.sparkle;
      case 'system_alert':
        return PhosphorIconsDuotone.warningCircle;
      default:
        return PhosphorIconsDuotone.bell;
    }
  }
}
