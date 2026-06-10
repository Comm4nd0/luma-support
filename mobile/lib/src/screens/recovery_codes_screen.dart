import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../repositories/me_repository.dart';
import '../services/api_client.dart';
import '../widgets/adaptive.dart';

/// Generate (and display once) a fresh set of 2FA recovery codes.
///
/// Plaintext lives only in this screen's state — leaving the screen
/// blanks the field. Users have to copy or screenshot before they
/// navigate away.
class RecoveryCodesScreen extends StatefulWidget {
  const RecoveryCodesScreen({super.key});

  @override
  State<RecoveryCodesScreen> createState() => _RecoveryCodesScreenState();
}

class _RecoveryCodesScreenState extends State<RecoveryCodesScreen> {
  List<String>? _codes;
  bool _busy = false;

  Future<void> _generate() async {
    final confirm = await confirmDialog(
      context,
      title: 'Regenerate codes?',
      message: 'Any existing recovery codes will be invalidated immediately. '
          'Save the new codes somewhere safe — they are only shown once.',
      confirmLabel: 'Regenerate',
      destructive: true,
    );
    if (!confirm) return;
    setState(() => _busy = true);
    try {
      final codes = await MeRepository(context.read<ApiClient>())
          .regenerateRecoveryCodes();
      if (!mounted) return;
      setState(() => _codes = codes);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Failed: $e')));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _copyAll() async {
    final codes = _codes;
    if (codes == null || codes.isEmpty) return;
    await Clipboard.setData(ClipboardData(text: codes.join('\n')));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Recovery codes copied to clipboard.')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final codes = _codes;
    return Scaffold(
      appBar: AppBar(title: const Text('Recovery codes')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text(
            'Recovery codes let you log in if you lose your authenticator. '
            'Each code is single-use. Save them somewhere safe — they are '
            'only shown once, immediately after generation.',
            style: TextStyle(height: 1.4),
          ),
          const SizedBox(height: 16),
          if (codes != null) ...[
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: SelectableText(
                  codes.join('\n'),
                  style: const TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 18,
                    height: 1.6,
                    letterSpacing: 1.5,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 8),
            OutlinedButton.icon(
              onPressed: _copyAll,
              icon: const Icon(Icons.copy_outlined),
              label: const Text('Copy all'),
            ),
            const SizedBox(height: 16),
            const Text(
              'Closing this screen will hide the codes for good.',
              style: TextStyle(fontSize: 12, color: Colors.white60),
            ),
          ],
          const SizedBox(height: 16),
          ElevatedButton.icon(
            onPressed: _busy ? null : _generate,
            icon: const Icon(Icons.refresh),
            label: Text(codes == null
                ? 'Generate recovery codes'
                : 'Regenerate codes'),
          ),
        ],
      ),
    );
  }
}
