import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../services/api_client.dart';
import '../services/api_paths.dart';

/// Admin-only revenue snapshot — parity with the portal's
/// /dashboard/revenue/ page.
class RevenueDashboardScreen extends StatefulWidget {
  const RevenueDashboardScreen({super.key});

  @override
  State<RevenueDashboardScreen> createState() => _RevenueDashboardScreenState();
}

class _RevenueDashboardScreenState extends State<RevenueDashboardScreen> {
  late Future<_RevenueData> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<_RevenueData> _load() async {
    final api = context.read<ApiClient>();
    try {
      final res = await api.dio.get<dynamic>(ApiPaths.revenueMetrics);
      return _RevenueData.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> _refresh() async {
    setState(() => _future = _load());
  }

  @override
  Widget build(BuildContext context) {
    final money = NumberFormat.simpleCurrency(name: 'GBP');
    return Scaffold(
      appBar: AppBar(title: const Text('Revenue')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<_RevenueData>(
          future: _future,
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snap.hasError) {
              return Center(child: Text('Error: ${snap.error}'));
            }
            final data = snap.data!;
            final maxMrr = data.history
                .map((m) => m.mrr)
                .fold<double>(0, (a, b) => b > a ? b : a);
            return ListView(
              padding: const EdgeInsets.all(12),
              children: [
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('Current MRR',
                            style: TextStyle(color: Colors.grey)),
                        const SizedBox(height: 4),
                        Text(
                          money.format(data.currentMrr),
                          style: const TextStyle(
                            fontSize: 32,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        Text(
                          'ARR ${money.format(data.arr)}',
                          style: const TextStyle(color: Colors.grey),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          '12-month MRR',
                          style: TextStyle(fontWeight: FontWeight.w600),
                        ),
                        const SizedBox(height: 12),
                        SizedBox(
                          height: 120,
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.end,
                            children: [
                              for (final m in data.history)
                                Expanded(
                                  child: Padding(
                                    padding:
                                        const EdgeInsets.symmetric(horizontal: 2),
                                    child: Column(
                                      mainAxisAlignment: MainAxisAlignment.end,
                                      children: [
                                        Container(
                                          height: maxMrr <= 0
                                              ? 2
                                              : (m.mrr / maxMrr * 100)
                                                  .clamp(2.0, 100.0),
                                          decoration: BoxDecoration(
                                            color: Theme.of(context)
                                                .colorScheme
                                                .primary,
                                            borderRadius:
                                                const BorderRadius.vertical(
                                              top: Radius.circular(4),
                                            ),
                                          ),
                                        ),
                                        const SizedBox(height: 2),
                                        Text(
                                          DateFormat('MMM')
                                              .format(m.month)
                                              .substring(0, 1),
                                          style: const TextStyle(fontSize: 10),
                                        ),
                                      ],
                                    ),
                                  ),
                                ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('Health',
                            style: TextStyle(fontWeight: FontWeight.w600)),
                        const SizedBox(height: 8),
                        _kv('Gross churn (90d)',
                            '${(data.grossChurn90 * 100).toStringAsFixed(1)}%'),
                        _kv('Net rev retention (12mo)',
                            '${(data.nrr12 * 100).toStringAsFixed(1)}%'),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('MRR by tier',
                            style: TextStyle(fontWeight: FontWeight.w600)),
                        const SizedBox(height: 8),
                        for (final entry in data.mrrByTier.entries)
                          _kv(entry.key, money.format(entry.value)),
                      ],
                    ),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  Widget _kv(String k, String v) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 2),
        child: Row(
          children: [
            Expanded(child: Text(k, style: const TextStyle(color: Colors.grey))),
            Text(v),
          ],
        ),
      );
}

class _RevenueData {
  _RevenueData({
    required this.currentMrr,
    required this.arr,
    required this.mrrByTier,
    required this.grossChurn90,
    required this.nrr12,
    required this.history,
  });

  final double currentMrr;
  final double arr;
  final Map<String, double> mrrByTier;
  final double grossChurn90;
  final double nrr12;
  final List<_MonthBucket> history;

  factory _RevenueData.fromJson(Map<String, dynamic> json) => _RevenueData(
        currentMrr: double.tryParse(json['current_mrr'].toString()) ?? 0,
        arr: double.tryParse(json['arr'].toString()) ?? 0,
        mrrByTier: ((json['mrr_by_tier'] as Map?) ?? const {})
            .map((k, v) => MapEntry(
                  k.toString(),
                  double.tryParse(v.toString()) ?? 0,
                )),
        grossChurn90:
            double.tryParse(json['gross_churn_90d'].toString()) ?? 0,
        nrr12: double.tryParse(json['nrr_12mo'].toString()) ?? 0,
        history: (json['history'] as List? ?? const [])
            .map((j) => _MonthBucket.fromJson(j as Map<String, dynamic>))
            .toList(),
      );
}

class _MonthBucket {
  _MonthBucket({required this.month, required this.mrr});
  final DateTime month;
  final double mrr;
  factory _MonthBucket.fromJson(Map<String, dynamic> json) => _MonthBucket(
        month: DateTime.tryParse(json['month'] as String? ?? '') ??
            DateTime.now(),
        mrr: double.tryParse(json['mrr'].toString()) ?? 0,
      );
}
