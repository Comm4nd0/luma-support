import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models/client.dart';
import '../models/client_document.dart';
import '../models/contact.dart';
import '../models/ticket.dart';
import '../repositories/client_documents_repository.dart';
import '../repositories/clients_repository.dart';
import '../repositories/invoices_repository.dart';
import '../repositories/site_visits_repository.dart';
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

  Future<void> _startSiteVisit() async {
    final messenger = ScaffoldMessenger.of(context);
    final repo = SiteVisitsRepository(context.read<ApiClient>());
    try {
      await repo.start(widget.clientId);
      if (!mounted) return;
      messenger.showSnackBar(
        SnackBar(
          content: const Text('Site visit started.'),
          action: SnackBarAction(
            label: 'Visits',
            onPressed: () => context.push('/site-visits'),
          ),
        ),
      );
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Failed to start: $e')));
    }
  }

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

  Future<void> _downloadMonthlyReport() async {
    final messenger = ScaffoldMessenger.of(context);
    final repo = ClientsRepository(context.read<ApiClient>());
    messenger.showSnackBar(
      const SnackBar(content: Text('Building this month’s report…')),
    );
    try {
      final path = await repo.downloadMonthlyReport(widget.clientId);
      if (!mounted) return;
      final opened = await launchUrl(Uri.file(path));
      if (!opened) {
        messenger.showSnackBar(
          SnackBar(content: Text('Saved report to $path')),
        );
      }
    } catch (e) {
      messenger.showSnackBar(
        SnackBar(content: Text('Report failed: $e')),
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
              tooltip: 'Timeline',
              icon: const Icon(Icons.history),
              onPressed: () =>
                  context.push('/clients/${widget.clientId}/timeline'),
            ),
          if (isStaff)
            IconButton(
              tooltip: 'Monthly report (PDF)',
              icon: const Icon(Icons.picture_as_pdf_outlined),
              onPressed: _downloadMonthlyReport,
            ),
          if (isStaff)
            IconButton(
              tooltip: 'Start site visit',
              icon: const Icon(Icons.location_on_outlined),
              onPressed: _startSiteVisit,
            ),
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
            length: 4,
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
                  isScrollable: true,
                  tabs: [
                    Tab(text: 'Systems'),
                    Tab(text: 'Contacts'),
                    Tab(text: 'Tickets'),
                    Tab(text: 'Docs'),
                  ],
                ),
                Expanded(
                  child: TabBarView(
                    children: [
                      _systemsTab(c),
                      _contactsTab(c),
                      _ticketsTab(data.tickets),
                      _DocumentsTab(clientId: widget.clientId, isStaff: isStaff),
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

class _DocumentsTab extends StatefulWidget {
  const _DocumentsTab({required this.clientId, required this.isStaff});
  final int clientId;
  final bool isStaff;

  @override
  State<_DocumentsTab> createState() => _DocumentsTabState();
}

class _DocumentsTabState extends State<_DocumentsTab> {
  late Future<List<ClientDocument>> _future;

  ClientDocumentsRepository get _repo =>
      ClientDocumentsRepository(context.read<ApiClient>());

  @override
  void initState() {
    super.initState();
    _future = _repo.list(clientId: widget.clientId);
  }

  Future<void> _refresh() async {
    setState(() => _future = _repo.list(clientId: widget.clientId));
  }

  Future<void> _open(ClientDocument doc) async {
    final url = Uri.parse(doc.fileUrl);
    if (await canLaunchUrl(url)) {
      await launchUrl(url, mode: LaunchMode.externalApplication);
    } else {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Couldn't open the file.")),
      );
    }
  }

  Future<void> _upload() async {
    final picker = ImagePicker();
    final picked = await picker.pickMedia();
    if (picked == null) return;
    final titleController =
        TextEditingController(text: picked.name);
    var kind = 'other';
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Upload document'),
        content: StatefulBuilder(
          builder: (ctx2, setLocal) => Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: titleController,
                decoration: const InputDecoration(labelText: 'Title'),
              ),
              const SizedBox(height: 8),
              DropdownButtonFormField<String>(
                value: kind,
                decoration: const InputDecoration(labelText: 'Kind'),
                items: const [
                  DropdownMenuItem(value: 'contract', child: Text('Contract')),
                  DropdownMenuItem(value: 'warranty', child: Text('Warranty')),
                  DropdownMenuItem(value: 'diagram', child: Text('Diagram')),
                  DropdownMenuItem(value: 'welcome', child: Text('Welcome pack')),
                  DropdownMenuItem(value: 'other', child: Text('Other')),
                ],
                onChanged: (v) => setLocal(() => kind = v ?? 'other'),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Upload'),
          ),
        ],
      ),
    );
    if (ok != true) return;
    final messenger = ScaffoldMessenger.of(context);
    try {
      await _repo.upload(
        clientId: widget.clientId,
        title: titleController.text.trim().isEmpty
            ? picked.name
            : titleController.text.trim(),
        file: File(picked.path),
        kind: kind,
      );
      messenger.showSnackBar(const SnackBar(content: Text('Uploaded.')));
      if (mounted) _refresh();
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Upload failed: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<List<ClientDocument>>(
          future: _future,
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snap.hasError) {
              return Center(child: Text('Error: ${snap.error}'));
            }
            final docs = snap.data ?? const <ClientDocument>[];
            if (docs.isEmpty) {
              return const _EmptyState('No documents yet.');
            }
            return ListView(
              padding: const EdgeInsets.all(12),
              children: [
                for (final d in docs)
                  Card(
                    margin: const EdgeInsets.only(bottom: 8),
                    child: ListTile(
                      leading: const Icon(Icons.description_outlined),
                      title: Text(d.title),
                      subtitle: Text(
                        '${d.kind.name}'
                        '${d.uploadedByEmail != null ? " · ${d.uploadedByEmail}" : ""}'
                        '${!d.clientVisible ? " · internal" : ""}',
                      ),
                      trailing: const Icon(Icons.open_in_new, size: 18),
                      onTap: () => _open(d),
                    ),
                  ),
              ],
            );
          },
        ),
      ),
      floatingActionButton: widget.isStaff
          ? FloatingActionButton.small(
              onPressed: _upload,
              tooltip: 'Upload document',
              child: const Icon(Icons.add),
            )
          : null,
    );
  }
}
