import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models/payment.dart';
import '../repositories/payments_repository.dart';
import '../services/api_client.dart';
import '../theme.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../../src/widgets/luma_icon.dart';

class PaymentsScreen extends StatefulWidget {
  const PaymentsScreen({super.key});

  @override
  State<PaymentsScreen> createState() => _PaymentsScreenState();
}

class _PaymentsScreenState extends State<PaymentsScreen> {
  late Future<List<Payment>> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<List<Payment>> _load() =>
      PaymentsRepository(context.read<ApiClient>()).list();

  Future<void> _refresh() async {
    setState(() {
      _future = _load();
    });
  }

  @override
  Widget build(BuildContext context) {
    final money = NumberFormat.simpleCurrency(name: 'GBP');
    return Scaffold(
      appBar: AppBar(
        title: const Text('Payments'),
        actions: [
          IconButton(
            icon: const LumaIcon(PhosphorIconsDuotone.arrowsClockwise),
            onPressed: _refresh,
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<List<Payment>>(
          future: _future,
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snap.hasError) {
              return Center(child: Text('Error: ${snap.error}'));
            }
            final items = snap.data ?? const <Payment>[];
            if (items.isEmpty) {
              return const Center(child: Text('No payments yet.'));
            }
            return ListView.builder(
              padding: const EdgeInsets.all(12),
              itemCount: items.length,
              itemBuilder: (_, i) {
                final p = items[i];
                return Card(
                  margin: const EdgeInsets.only(bottom: 8),
                  child: ListTile(
                    leading: const CircleAvatar(
                      backgroundColor: Color(0x3322C55E),
                      child: LumaIcon(PhosphorIconsDuotone.money, color: Color(0xFF22C55E)),
                    ),
                    title: Text(money.format(p.amount)),
                    subtitle: Text(
                      'Invoice #${p.invoiceId}'
                      '${p.reference.isEmpty ? '' : ' · ${p.reference}'}',
                      style: const TextStyle(color: kMuted),
                    ),
                    trailing: Text(
                      p.paidAt == null
                          ? '—'
                          : DateFormat.yMMMd().format(p.paidAt!),
                      style: const TextStyle(fontSize: 12),
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
