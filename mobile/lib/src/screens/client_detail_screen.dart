import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import 'package:flutter/services.dart';

import '../models/client.dart';
import '../models/contact.dart';
import '../models/ticket.dart';
import '../repositories/clients_repository.dart';
import '../repositories/invoices_repository.dart';
import '../repositories/tickets_repository.dart';
import '../services/api_client.dart';
import '../services/current_user.dart';
import 'contact_form_screen.dart';
import 'widgets/ticket_tile.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../../src/widgets/luma_icon.dart';

class ClientDetailScreen extends StatefulWidget {
  const ClientDetailScreen({super.key, required this.clientId});

  final int clientId;

  @override
  State<ClientDetailScreen> createState() => _ClientDetailScreenState();
}

class _ClientDetailScreenState extends State<ClientDetailScreen> {
  late Future<_ClientDetailData> _future;

  Future<void> _showHealthBreakdown(Client c) async {
    final repo = ClientsRepository(context.read<ApiClient>());
    final messenger = ScaffoldMessenger.of(context);
    try {
      final h = await repo.health(c.id);
      if (!mounted) return;
      await showModalBottomSheet<void>(
        context: context,
        builder: (_) => SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Health ${h.score} / 100 (${h.band})',
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 12),
                _kv('CSAT (90d avg)', h.csat == null ? '—' : '${h.csat!.toStringAsFixed(1)} / 5'),
                _kv('Open tickets', h.openTickets.toString()),
                _kv('Overdue invoices', h.overdueInvoices.toString()),
                _kv(
                  'Systems OK',
                  h.systemsOkPct == null
                      ? '— (nothing monitored)'
                      : '${(h.systemsOkPct! * 100).round()}%',
                ),
                if (h.reasons.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  const Text('Why', style: TextStyle(fontWeight: FontWeight.w600)),
                  const SizedBox(height: 4),
                  for (final reason in h.reasons)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 2),
                      child: Text('• $reason'),
                    ),
                ],
              ],
            ),
          ),
        ),
      );
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Health failed: $e')));
    }
  }

  Widget _kv(String key, String value) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 2),
        child: Row(
          children: [
            SizedBox(width: 160, child: Text(key, style: const TextStyle(color: Colors.white70))),
            Expanded(child: Text(value)),
          ],
        ),
      );

  Future<void> _openStripePortal() async {
    final messenger = ScaffoldMessenger.of(context);
    final repo = InvoicesRepository(context.read<ApiClient>());
    try {
      final url = await repo.stripeCustomerPortal(
        clientId: widget.clientId,
        // Mobile has no equivalent of window.location for the return,
        // so we hand Stripe the canonical web client detail URL.
        returnUrl: 'https://lumatechsolutions.co.uk/clients/${widget.clientId}/',
      );
      if (!mounted) return;
      if (url == null || url.isEmpty) {
        messenger.showSnackBar(
          const SnackBar(
            content: Text('Stripe is not configured on this server.'),
          ),
        );
        return;
      }
      await Clipboard.setData(ClipboardData(text: url));
      messenger.showSnackBar(
        const SnackBar(
          content: Text(
            'Stripe portal URL copied to clipboard — paste into your browser to open.',
          ),
        ),
      );
    } catch (e) {
      messenger.showSnackBar(
        SnackBar(content: Text('Failed to open Stripe portal: $e')),
      );
    }
  }

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<_ClientDetailData> _load() async {
    final api = context.read<ApiClient>();
    final client = await ClientsRepository(api).get(widget.clientId);
    // Tickets aren't nested in the client serializer, so fetch separately.
    // The viewset filters by `client` query param.
    final tickets = await TicketsRepository(api).list();
    return _ClientDetailData(
      client: client,
      tickets: tickets.where((t) => t.clientId == widget.clientId).toList(),
    );
  }

  Future<void> _openContactForm({Contact? contact}) async {
    final saved = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => ContactFormScreen(
          clientId: widget.clientId,
          contact: contact,
        ),
      ),
    );
    if (saved == true) {
      setState(() => _future = _load());
    }
  }

  @override
  Widget build(BuildContext context) {
    final isStaff = context.watch<CurrentUser>().isStaff;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Client'),
        actions: [
          if (isStaff)
            IconButton(
              tooltip: 'Stripe portal',
              icon: const Icon(Icons.payments_outlined),
              onPressed: _openStripePortal,
            ),
          if (isStaff)
            IconButton(
              tooltip: 'Edit',
              icon: const Icon(Icons.edit_outlined),
              onPressed: () =>
                  context.push('/clients/${widget.clientId}/edit'),
            ),
        ],
      ),
      body: FutureBuilder<_ClientDetailData>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return Center(child: Text('Error: ${snap.error}'));
          }
          final data = snap.data!;
          final c = data.client;
          return DefaultTabController(
            length: 3,
            child: Column(
              children: [
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(c.name,
                          style: const TextStyle(
                              fontSize: 22, fontWeight: FontWeight.w600)),
                      if (c.company.isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 2),
                          child: Text(c.company,
                              style: const TextStyle(color: Colors.grey)),
                        ),
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 8,
                        runSpacing: 4,
                        children: [
                          if (c.email.isNotEmpty) Chip(label: Text(c.email)),
                          if (c.phone.isNotEmpty) Chip(label: Text(c.phone)),
                          Chip(label: Text('Plan: ${c.carePlanTier}')),
                          if (isStaff)
                            ActionChip(
                              avatar: const Icon(Icons.favorite_outline, size: 16),
                              label: const Text('Health'),
                              onPressed: () => _showHealthBreakdown(c),
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
                const TabBar(
                  tabs: [
                    Tab(text: 'Systems'),
                    Tab(text: 'Contacts'),
                    Tab(text: 'Tickets'),
                  ],
                ),
                Expanded(
                  child: TabBarView(
                    children: [
                      _systemsTab(c),
                      _contactsTab(c),
                      _ticketsTab(data.tickets),
                    ],
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _systemsTab(Client c) {
    if (c.systems.isEmpty) {
      return const _EmptyState('No systems on file.');
    }
    return ListView(
      padding: const EdgeInsets.all(12),
      children: [
        for (final s in c.systems)
          Card(
            margin: const EdgeInsets.only(bottom: 8),
            child: ListTile(
              leading: const LumaIcon(PhosphorIconsDuotone.cpu),
              title: Text(s.name),
              subtitle: Text('${s.type} · ${s.description}',
                  maxLines: 2, overflow: TextOverflow.ellipsis),
            ),
          ),
      ],
    );
  }

  Widget _contactsTab(Client c) {
    final isStaff = context.read<CurrentUser>().isStaff;
    final children = <Widget>[
      if (isStaff)
        Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: OutlinedButton.icon(
            onPressed: () => _openContactForm(),
            icon: const Icon(Icons.add),
            label: const Text('Add contact'),
          ),
        ),
      if (c.contacts.isEmpty)
        const _EmptyState('No contacts on file.')
      else
        for (final ct in c.contacts)
          Card(
            margin: const EdgeInsets.only(bottom: 8),
            child: ListTile(
              leading: CircleAvatar(
                  child: Text(ct.name.isNotEmpty ? ct.name[0] : '?')),
              title: Text(ct.name),
              subtitle: Text([
                if (ct.title.isNotEmpty) ct.title,
                if (ct.email.isNotEmpty) ct.email,
                if (ct.phone.isNotEmpty) ct.phone,
              ].join(' · ')),
              trailing: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (ct.isPrimary) const Chip(label: Text('Primary')),
                  if (isStaff)
                    IconButton(
                      icon: const Icon(Icons.edit_outlined),
                      onPressed: () => _openContactForm(contact: ct),
                    ),
                ],
              ),
              onTap:
                  isStaff ? () => _openContactForm(contact: ct) : null,
            ),
          ),
    ];
    return ListView(
      padding: const EdgeInsets.all(12),
      children: children,
    );
  }

  Widget _ticketsTab(List<Ticket> tickets) {
    if (tickets.isEmpty) {
      return const _EmptyState('No tickets for this client.');
    }
    return ListView(
      padding: const EdgeInsets.all(12),
      children: [
        for (final t in tickets)
          TicketTile(ticket: t, onTap: () => context.push('/tickets/${t.id}')),
      ],
    );
  }
}

class _ClientDetailData {
  _ClientDetailData({required this.client, required this.tickets});
  final Client client;
  final List<Ticket> tickets;
}

class _EmptyState extends StatelessWidget {
  const _EmptyState(this.message);
  final String message;
  @override
  Widget build(BuildContext context) => Center(
        child: Text(message, style: const TextStyle(color: Colors.grey)),
      );
}
