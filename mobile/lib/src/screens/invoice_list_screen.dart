import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../models/invoice.dart';
import '../repositories/invoices_repository.dart';
import '../services/api_client.dart';
import 'widgets/client_picker.dart';
import 'widgets/invoice_tile.dart';
import 'widgets/luma_drawer.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../../src/widgets/luma_icon.dart';

class InvoiceListScreen extends StatefulWidget {
  const InvoiceListScreen({super.key});

  @override
  State<InvoiceListScreen> createState() => _InvoiceListScreenState();
}

class _InvoiceListScreenState extends State<InvoiceListScreen> {
  InvoiceStatus? _status;
  late Future<List<Invoice>> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<List<Invoice>> _load() =>
      InvoicesRepository(context.read<ApiClient>()).list(status: _status);

  Future<void> _refresh() async {
    setState(() {
      _future = _load();
    });
  }

  void _setStatus(InvoiceStatus? s) {
    setState(() {
      _status = s;
      _future = _load();
    });
  }

  Future<void> _showCreateMenu() async {
    final choice = await showModalBottomSheet<String>(
      context: context,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const LumaIcon(PhosphorIconsDuotone.notePencil),
              title: const Text('New one-off invoice'),
              subtitle: const Text('Pick a client and add lines.'),
              onTap: () => Navigator.pop(ctx, 'create'),
            ),
            ListTile(
              leading: const LumaIcon(PhosphorIconsDuotone.clock),
              title: const Text('Generate from time entries'),
              subtitle: const Text(
                'Bundle a client\'s unbilled time into a draft invoice.',
              ),
              onTap: () => Navigator.pop(ctx, 'from_time'),
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
    if (!mounted) return;
    if (choice == 'create') {
      await context.push('/billing/invoices/new');
      _refresh();
    } else if (choice == 'from_time') {
      await _generateFromTime();
    }
  }

  Future<void> _generateFromTime() async {
    final api = context.read<ApiClient>();
    final client = await showClientPicker(context, api);
    if (client == null || !mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    try {
      final inv = await InvoicesRepository(api).generateFromTime(client.id);
      messenger.showSnackBar(
        SnackBar(content: Text('Created draft invoice #${inv.id}')),
      );
      if (mounted) {
        await context.push('/billing/invoices/${inv.id}');
        _refresh();
      }
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('$e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Invoices'),
        actions: [
          IconButton(
            icon: const LumaIcon(PhosphorIconsDuotone.money),
            tooltip: 'Payments',
            onPressed: () => context.push('/billing/payments'),
          ),
          IconButton(
            icon: const LumaIcon(PhosphorIconsDuotone.arrowsClockwise),
            onPressed: _refresh,
          ),
        ],
      ),
      drawer: const LumaDrawer(),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showCreateMenu,
        icon: const LumaIcon(PhosphorIconsDuotone.plus),
        label: const Text('New invoice'),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 4),
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  _StatusChip(
                    label: 'All',
                    selected: _status == null,
                    onTap: () => _setStatus(null),
                  ),
                  for (final s in const [
                    InvoiceStatus.draft,
                    InvoiceStatus.sent,
                    InvoiceStatus.authorised,
                    InvoiceStatus.paid,
                    InvoiceStatus.voided,
                  ])
                    _StatusChip(
                      label: s.name,
                      selected: _status == s,
                      onTap: () => _setStatus(s),
                    ),
                ],
              ),
            ),
          ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: _refresh,
              child: FutureBuilder<List<Invoice>>(
                future: _future,
                builder: (context, snapshot) {
                  if (snapshot.connectionState != ConnectionState.done) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  if (snapshot.hasError) {
                    return Center(child: Text('Error: ${snapshot.error}'));
                  }
                  final items = snapshot.data ?? const <Invoice>[];
                  if (items.isEmpty) {
                    return const Center(child: Text('No invoices.'));
                  }
                  return ListView.builder(
                    padding: const EdgeInsets.all(12),
                    itemCount: items.length,
                    itemBuilder: (_, i) {
                      final inv = items[i];
                      return InvoiceTile(
                        invoice: inv,
                        onTap: () async {
                          await context.push('/billing/invoices/${inv.id}');
                          if (mounted) _refresh();
                        },
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

class _StatusChip extends StatelessWidget {
  const _StatusChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: ChoiceChip(
        label: Text(label),
        selected: selected,
        onSelected: (_) => onTap(),
      ),
    );
  }
}
