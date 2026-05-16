import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models/ticket.dart';
import '../repositories/tickets_repository.dart';
import '../services/api_client.dart';
import '../services/current_user.dart';
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
                Card(
                  margin: const EdgeInsets.only(bottom: 4),
                  child: ListTile(
                    leading: const LumaIcon(PhosphorIconsDuotone.calendar),
                    title: const Text('Maintenance schedules'),
                    subtitle: const Text(
                        'Recurring work that auto-generates tickets'),
                    trailing: const LumaIcon(PhosphorIconsDuotone.caretRight),
                    onTap: () => context.push('/maintenance'),
                  ),
                ),
                if (currentUser.isAdmin)
                  Card(
                    margin: const EdgeInsets.only(bottom: 4),
                    child: ListTile(
                      leading: const LumaIcon(PhosphorIconsDuotone.receipt),
                      title: const Text('Billing'),
                      subtitle: const Text(
                          'Manage invoices and sync to Xero'),
                      trailing: const LumaIcon(PhosphorIconsDuotone.caretRight),
                      onTap: () => context.push('/billing/invoices'),
                    ),
                  ),
                if (currentUser.isAdmin)
                  Card(
                    margin: const EdgeInsets.only(bottom: 8),
                    child: ListTile(
                      leading: const LumaIcon(PhosphorIconsDuotone.shieldCheck),
                      title: const Text('Audit log'),
                      subtitle: const Text(
                          'Who did what — credential + billing actions'),
                      trailing: const LumaIcon(PhosphorIconsDuotone.caretRight),
                      onTap: () => context.push('/audit'),
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
