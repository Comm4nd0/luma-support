import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models/social_inbox_item.dart';
import '../repositories/social_repository.dart';
import '../services/api_client.dart';
import '../widgets/luma_icon.dart';
import 'widgets/luma_drawer.dart';

class SocialInboxScreen extends StatefulWidget {
  const SocialInboxScreen({super.key});

  @override
  State<SocialInboxScreen> createState() => _SocialInboxScreenState();
}

class _SocialInboxScreenState extends State<SocialInboxScreen> {
  late Future<List<SocialInboxItem>> _future;

  SocialRepository get _repo => SocialRepository(context.read<ApiClient>());

  @override
  void initState() {
    super.initState();
    _future = _repo.listInbox();
  }

  Future<void> _refresh() async {
    setState(() => _future = _repo.listInbox());
  }

  Future<void> _dismiss(SocialInboxItem item) async {
    try {
      await _repo.dismiss(item.id);
      await _refresh();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Dismiss failed: $e')),
        );
      }
    }
  }

  Future<void> _convertToTicket(SocialInboxItem item) async {
    try {
      final ticketId = await _repo.convertToTicket(item.id);
      await _refresh();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Created ticket #$ticketId')),
        );
        context.push('/tickets/$ticketId');
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Convert failed: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Social inbox')),
      drawer: const LumaDrawer(),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<List<SocialInboxItem>>(
          future: _future,
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snap.hasError) {
              return Center(child: Text('Error: ${snap.error}'));
            }
            final items = snap.data ?? const <SocialInboxItem>[];
            if (items.isEmpty) {
              return const Center(
                child: Padding(
                  padding: EdgeInsets.all(16),
                  child: Text('Inbox zero on every connected account.'),
                ),
              );
            }
            return ListView.separated(
              padding: const EdgeInsets.symmetric(vertical: 8),
              itemCount: items.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (context, i) => _InboxTile(
                item: items[i],
                onDismiss: () => _dismiss(items[i]),
                onConvert: () => _convertToTicket(items[i]),
              ),
            );
          },
        ),
      ),
    );
  }
}

class _InboxTile extends StatelessWidget {
  const _InboxTile({
    required this.item,
    required this.onDismiss,
    required this.onConvert,
  });

  final SocialInboxItem item;
  final VoidCallback onDismiss;
  final VoidCallback onConvert;

  @override
  Widget build(BuildContext context) {
    final age = item.receivedAt == null
        ? '—'
        : _ageString(DateTime.now().difference(item.receivedAt!));
    final author = item.authorDisplay.isNotEmpty
        ? item.authorDisplay
        : (item.authorHandle.isNotEmpty ? '@${item.authorHandle}' : 'unknown');
    return ListTile(
      isThreeLine: true,
      leading: const LumaIcon(PhosphorIconsDuotone.chatCircleDots),
      title: Text('${item.kindDisplay} · $author'),
      subtitle: Padding(
        padding: const EdgeInsets.only(top: 4),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              item.preview.isEmpty ? '(no message body)' : item.preview,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 4),
            Text(
              '${item.accountDisplay.isNotEmpty ? item.accountDisplay : item.accountPlatform} · $age',
              style: const TextStyle(color: Colors.grey, fontSize: 12),
            ),
          ],
        ),
      ),
      trailing: PopupMenuButton<String>(
        onSelected: (value) async {
          switch (value) {
            case 'open':
              if (item.permalink.isNotEmpty) {
                final uri = Uri.tryParse(item.permalink);
                if (uri != null) {
                  await launchUrl(uri, mode: LaunchMode.externalApplication);
                }
              }
              break;
            case 'convert':
              onConvert();
              break;
            case 'dismiss':
              onDismiss();
              break;
          }
        },
        itemBuilder: (_) => [
          if (item.permalink.isNotEmpty)
            const PopupMenuItem(value: 'open', child: Text('Open in app')),
          const PopupMenuItem(value: 'convert', child: Text('Convert to ticket')),
          const PopupMenuItem(value: 'dismiss', child: Text('Dismiss')),
        ],
      ),
    );
  }

  String _ageString(Duration d) {
    if (d.inDays >= 1) return '${d.inDays}d ago';
    if (d.inHours >= 1) return '${d.inHours}h ago';
    if (d.inMinutes >= 1) return '${d.inMinutes}m ago';
    return 'just now';
  }
}
