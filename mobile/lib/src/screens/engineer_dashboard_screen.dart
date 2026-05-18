import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models/social_account.dart';
import '../models/ticket.dart';
import '../repositories/tickets_repository.dart';
import '../services/api_client.dart';
import '../services/current_user.dart';
import 'widgets/luma_drawer.dart';
import 'widgets/ticket_tile.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../../src/widgets/luma_icon.dart';

class EngineerDashboardScreen extends StatefulWidget {
  const EngineerDashboardScreen({super.key});

  @override
  State<EngineerDashboardScreen> createState() => _EngineerDashboardScreenState();
}

class _EngineerDashboardScreenState extends State<EngineerDashboardScreen> {
  late Future<_DashboardData> _future;

  TicketsRepository get _tickets => TicketsRepository(context.read<ApiClient>());

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<_DashboardData> _load() async {
    final all = await _tickets.list();
    DashboardStats? stats;
    try {
      stats = await _tickets.dashboardStats();
    } catch (_) {
      // KPIs are nice-to-have on dashboard load; never block on them.
    }
    return _DashboardData(
      slaWarnings: all.where((t) => t.isBreached || _withinWindow(t)).toList(),
      open: all
          .where((t) =>
              t.status != TicketStatus.resolved &&
              t.status != TicketStatus.closed)
          .toList(),
      stats: stats,
    );
  }

  bool _withinWindow(Ticket t) {
    final deadline = t.slaDeadline;
    if (deadline == null) return false;
    return deadline.difference(DateTime.now()).inMinutes <= 30;
  }

  Future<void> _refresh() async {
    setState(() => _future = _load());
  }

  @override
  Widget build(BuildContext context) {
    final currentUser = context.watch<CurrentUser>();
    final user = currentUser.user;
    return Scaffold(
      appBar: AppBar(
        title: Text(user == null ? 'Dashboard' : 'Hi ${user.firstName.isEmpty ? user.email : user.firstName}'),
        actions: [
          IconButton(
            icon: const LumaIcon(PhosphorIconsDuotone.plus),
            onPressed: () => context.push('/tickets/new'),
          ),
        ],
      ),
      drawer: const LumaDrawer(),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<_DashboardData>(
          future: _future,
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snap.hasError) {
              return Center(child: Text('Error: ${snap.error}'));
            }
            final data = snap.data!;
            return ListView(
              padding: const EdgeInsets.all(12),
              children: [
                if (data.stats != null) ...[
                  _KpiGrid(stats: data.stats!),
                  const SizedBox(height: 8),
                ],
                if (data.stats != null &&
                    data.stats!.socialAccounts.isNotEmpty) ...[
                  _SocialStrip(stats: data.stats!),
                  const SizedBox(height: 8),
                ],
                Card(
                  margin: const EdgeInsets.only(bottom: 8),
                  child: ListTile(
                    leading: const LumaIcon(PhosphorIconsDuotone.users),
                    title: const Text('Clients'),
                    subtitle: const Text(
                        'Browse and manage client records'),
                    trailing: const LumaIcon(PhosphorIconsDuotone.caretRight),
                    onTap: () => context.push('/clients'),
                  ),
                ),
                _SectionHeader(
                  'SLA warnings',
                  count: data.slaWarnings.length,
                  highlight: data.slaWarnings.isNotEmpty,
                ),
                if (data.slaWarnings.isEmpty)
                  const _EmptyHint('Nothing urgent right now.')
                else
                  for (final t in data.slaWarnings)
                    TicketTile(ticket: t, onTap: () => context.push('/tickets/${t.id}')),
                const SizedBox(height: 8),
                _SectionHeader('Open tickets', count: data.open.length),
                if (data.open.isEmpty)
                  const _EmptyHint('Inbox zero.')
                else
                  for (final t in data.open.take(20))
                    TicketTile(ticket: t, onTap: () => context.push('/tickets/${t.id}')),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _DashboardData {
  _DashboardData({
    required this.slaWarnings,
    required this.open,
    required this.stats,
  });
  final List<Ticket> slaWarnings;
  final List<Ticket> open;
  final DashboardStats? stats;
}

class _KpiGrid extends StatelessWidget {
  const _KpiGrid({required this.stats});
  final DashboardStats stats;

  @override
  Widget build(BuildContext context) {
    final money = NumberFormat.simpleCurrency(name: stats.currency);
    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      childAspectRatio: 2.5,
      mainAxisSpacing: 8,
      crossAxisSpacing: 8,
      children: [
        _KpiCard(label: 'Unbilled hours', value: stats.unbilledHours.toStringAsFixed(1)),
        _KpiCard(label: 'MTD invoiced', value: money.format(stats.mtdInvoiced)),
        _KpiCard(label: 'MTD paid', value: money.format(stats.mtdPaid)),
        _KpiCard(label: 'Overdue', value: '${stats.overdueInvoices}'),
        _KpiCard(
          label: 'Maintenance (7d)',
          value: '${stats.maintenanceDue7d}',
        ),
      ],
    );
  }
}

class _KpiCard extends StatelessWidget {
  const _KpiCard({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              label,
              style: const TextStyle(fontSize: 12, color: Colors.grey),
            ),
            const SizedBox(height: 2),
            Text(
              value,
              style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader(this.label, {this.count, this.highlight = false});
  final String label;
  final int? count;
  final bool highlight;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 12, 4, 8),
      child: Row(
        children: [
          Text(label,
              style: TextStyle(
                fontWeight: FontWeight.w600,
                color: highlight ? Colors.redAccent : null,
              )),
          if (count != null) ...[
            const SizedBox(width: 6),
            Text('($count)',
                style: TextStyle(
                  color: highlight ? Colors.redAccent : Colors.grey,
                )),
          ],
        ],
      ),
    );
  }
}

class _EmptyHint extends StatelessWidget {
  const _EmptyHint(this.message);
  final String message;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.all(16),
        child: Text(message, style: const TextStyle(color: Colors.grey)),
      );
}

class _SocialStrip extends StatelessWidget {
  const _SocialStrip({required this.stats});
  final DashboardStats stats;

  @override
  Widget build(BuildContext context) {
    final unhealthy =
        stats.socialAccounts.where((a) => !a.isHealthy).toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const _SectionHeader('Social accounts'),
        if (unhealthy.isNotEmpty)
          Card(
            color: Colors.red.withValues(alpha: 0.08),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Text(
                'Attention: ${unhealthy.map((a) => '${a.platformDisplay} (${a.healthStatus.isEmpty ? "unknown" : a.healthStatus})').join(' · ')}',
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
            ),
          ),
        GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          childAspectRatio: 2.0,
          mainAxisSpacing: 8,
          crossAxisSpacing: 8,
          children: [
            for (final a in stats.socialAccounts) _SocialKpiCard(account: a),
          ],
        ),
        const SizedBox(height: 8),
        Card(
          margin: EdgeInsets.zero,
          child: ListTile(
            leading:
                const LumaIcon(PhosphorIconsDuotone.chatCircleDots),
            title: const Text('Social inbox'),
            subtitle: Text(
              stats.socialInboxUnread == 0
                  ? 'Inbox zero on every connected account.'
                  : '${stats.socialInboxUnread} unanswered — DMs, mentions, comments',
            ),
            trailing: const LumaIcon(PhosphorIconsDuotone.caretRight),
            onTap: () => context.push('/social/inbox'),
          ),
        ),
      ],
    );
  }
}

class _SocialKpiCard extends StatelessWidget {
  const _SocialKpiCard({required this.account});
  final SocialAccountSummary account;

  @override
  Widget build(BuildContext context) {
    final delta = account.followersDelta7d;
    final days = account.daysSinceLastPost;
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              account.platformDisplay,
              style: const TextStyle(fontSize: 12, color: Colors.grey),
            ),
            const SizedBox(height: 2),
            Row(
              children: [
                Text(
                  account.followers == null
                      ? '—'
                      : '${account.followers}',
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                if (delta != null) ...[
                  const SizedBox(width: 6),
                  Text(
                    '${delta >= 0 ? '+' : ''}$delta / 7d',
                    style: TextStyle(
                      fontSize: 12,
                      color: delta >= 0 ? Colors.green : Colors.redAccent,
                    ),
                  ),
                ],
              ],
            ),
            const SizedBox(height: 2),
            Text(
              days == null
                  ? 'No posts seen'
                  : (days > 14
                      ? 'Last post ${days}d ago — stale'
                      : 'Last post ${days}d ago'),
              style: TextStyle(
                fontSize: 11,
                color: (days != null && days > 14)
                    ? Colors.redAccent
                    : Colors.grey,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
