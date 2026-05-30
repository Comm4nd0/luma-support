import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../repositories/me_repository.dart';
import '../services/api_client.dart';
import '../services/current_user.dart';

/// Self-enrol in TOTP two-factor auth from the device — parity with the
/// portal's session-based 2FA setup. Mobile has no QR widget, so we hand
/// the otpauth:// URI straight to an installed authenticator app and also
/// show the secret for manual entry. On confirmation we surface the fresh
/// recovery codes once.
class TotpSetupScreen extends StatefulWidget {
  const TotpSetupScreen({super.key});

  @override
  State<TotpSetupScreen> createState() => _TotpSetupScreenState();
}

class _TotpSetupScreenState extends State<TotpSetupScreen> {
  final _codeController = TextEditingController();
  MeRepository get _repo => MeRepository(context.read<ApiClient>());

  TotpSetup? _setup;
  List<String>? _recoveryCodes;
  String? _error;
  bool _busy = false;

  bool get _alreadyEnabled =>
      context.read<CurrentUser>().user?.totpEnabled ?? false;

  @override
  void initState() {
    super.initState();
    if (!_alreadyEnabled) _begin();
  }

  @override
  void dispose() {
    _codeController.dispose();
    super.dispose();
  }

  Future<void> _begin() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final setup = await _repo.setupTotp();
      if (!mounted) return;
      setState(() => _setup = setup);
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = 'Could not start enrolment: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _confirm() async {
    final code = _codeController.text.trim();
    if (code.isEmpty) return;
    final currentUser = context.read<CurrentUser>();
    final api = context.read<ApiClient>();
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final codes = await _repo.confirmTotp(code);
      // Refresh the cached user so totp_enabled flips on everywhere.
      await currentUser.fetch(api);
      if (!mounted) return;
      setState(() => _recoveryCodes = codes);
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = 'That code did not match. Try the current one.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _openInAuthenticator() async {
    final uri = _setup?.otpauthUri;
    if (uri == null || uri.isEmpty) return;
    await launchUrl(Uri.parse(uri), mode: LaunchMode.externalApplication);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Two-factor authentication')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (_alreadyEnabled)
            const _DoneCard(
              message:
                  'Two-factor authentication is already on for this account.',
            )
          else if (_recoveryCodes != null)
            _RecoveryCodes(codes: _recoveryCodes!)
          else ...[
            const Text(
              'Add this account to an authenticator app, then enter the '
              '6-digit code it shows to switch on two-factor auth.',
              style: TextStyle(height: 1.4),
            ),
            const SizedBox(height: 16),
            if (_busy && _setup == null)
              const Center(child: CircularProgressIndicator())
            else if (_setup != null) ...[
              FilledButton.icon(
                onPressed: _openInAuthenticator,
                icon: const Icon(Icons.open_in_new),
                label: const Text('Open in authenticator app'),
              ),
              const SizedBox(height: 12),
              const Text('Or enter this key manually:',
                  style: TextStyle(fontSize: 12)),
              const SizedBox(height: 4),
              Card(
                child: ListTile(
                  title: SelectableText(
                    _setup!.secret,
                    style: const TextStyle(
                        fontFamily: 'monospace', letterSpacing: 1.5),
                  ),
                  trailing: IconButton(
                    icon: const Icon(Icons.copy_outlined),
                    onPressed: () async {
                      await Clipboard.setData(
                          ClipboardData(text: _setup!.secret));
                      if (!mounted) return;
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Key copied.')),
                      );
                    },
                  ),
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _codeController,
                keyboardType: TextInputType.number,
                maxLength: 6,
                decoration: const InputDecoration(
                  labelText: '6-digit code',
                  border: OutlineInputBorder(),
                ),
              ),
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(_error!,
                      style: const TextStyle(color: Colors.redAccent)),
                ),
              const SizedBox(height: 8),
              FilledButton(
                onPressed: _busy ? null : _confirm,
                child: const Text('Turn on two-factor auth'),
              ),
            ] else if (_error != null)
              Text(_error!,
                  style: const TextStyle(color: Colors.redAccent)),
          ],
        ],
      ),
    );
  }
}

class _DoneCard extends StatelessWidget {
  const _DoneCard({required this.message});
  final String message;

  @override
  Widget build(BuildContext context) {
    return Card(
      color: Colors.green.withValues(alpha: 0.10),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            const Icon(Icons.check_circle_outline, color: Colors.green),
            const SizedBox(width: 12),
            Expanded(child: Text(message)),
          ],
        ),
      ),
    );
  }
}

class _RecoveryCodes extends StatelessWidget {
  const _RecoveryCodes({required this.codes});
  final List<String> codes;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const _DoneCard(message: 'Two-factor auth is on. 🎉'),
        const SizedBox(height: 16),
        const Text(
          'Save these recovery codes somewhere safe — each is single-use and '
          'they are only shown once. Use one if you lose your authenticator.',
          style: TextStyle(height: 1.4),
        ),
        const SizedBox(height: 12),
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
          onPressed: () async {
            await Clipboard.setData(ClipboardData(text: codes.join('\n')));
            if (!context.mounted) return;
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Recovery codes copied.')),
            );
          },
          icon: const Icon(Icons.copy_outlined),
          label: const Text('Copy all'),
        ),
      ],
    );
  }
}
