import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models/referral_code.dart';
import '../repositories/referrals_repository.dart';
import '../services/api_client.dart';

/// Client-facing "Refer a friend" screen — parity with the portal's
/// /portal/refer/ page.
class ReferScreen extends StatefulWidget {
  const ReferScreen({super.key});

  @override
  State<ReferScreen> createState() => _ReferScreenState();
}

class _ReferScreenState extends State<ReferScreen> {
  late Future<ReferralCode> _future;

  ReferralsRepository get _repo =>
      ReferralsRepository(context.read<ApiClient>());

  @override
  void initState() {
    super.initState();
    _future = _repo.myCode();
  }

  Future<void> _refresh() async {
    setState(() => _future = _repo.myCode());
  }

  @override
  Widget build(BuildContext context) {
    final fmt = DateFormat('yyyy-MM-dd');
    return Scaffold(
      appBar: AppBar(title: const Text('Refer a friend')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<ReferralCode>(
          future: _future,
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snap.hasError) {
              return Center(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Text(
                    "We couldn't load your referral code. Tap to retry.\n${snap.error}",
                    textAlign: TextAlign.center,
                  ),
                ),
              );
            }
            final code = snap.data!;
            return ListView(
              padding: const EdgeInsets.all(12),
              children: [
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Your link',
                          style: TextStyle(fontWeight: FontWeight.w600),
                        ),
                        const SizedBox(height: 8),
                        SelectableText(
                          code.shareLink,
                          style: const TextStyle(fontSize: 14),
                        ),
                        const SizedBox(height: 12),
                        Row(
                          children: [
                            ElevatedButton.icon(
                              icon: const Icon(Icons.copy),
                              label: const Text('Copy link'),
                              onPressed: () async {
                                await Clipboard.setData(
                                  ClipboardData(text: code.shareLink),
                                );
                                if (!mounted) return;
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(
                                    content: Text('Link copied to clipboard.'),
                                  ),
                                );
                              },
                            ),
                            const SizedBox(width: 8),
                            Text(
                              'Code: ${code.code}',
                              style: const TextStyle(color: Colors.grey),
                            ),
                          ],
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
                          'Your credit',
                          style: TextStyle(fontWeight: FontWeight.w600),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          '£${code.creditBalance}',
                          style: const TextStyle(
                            fontSize: 32,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        Text(
                          'Applied to your next monthly invoice. '
                          'Lifetime earned: £${code.lifetimeCredit}.',
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
                          "People you've referred",
                          style: TextStyle(fontWeight: FontWeight.w600),
                        ),
                        const SizedBox(height: 6),
                        if (code.referrals.isEmpty)
                          const Padding(
                            padding: EdgeInsets.symmetric(vertical: 8),
                            child: Text(
                              'No referrals yet — share the link above!',
                              style: TextStyle(color: Colors.grey),
                            ),
                          )
                        else
                          for (final r in code.referrals)
                            ListTile(
                              contentPadding: EdgeInsets.zero,
                              dense: true,
                              title: Text(r.name),
                              subtitle: Text(
                                '${r.stageDisplay} · ${fmt.format(r.createdAt)}',
                              ),
                            ),
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
}
