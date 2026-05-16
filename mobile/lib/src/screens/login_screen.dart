import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../services/auth_service.dart';
import '../theme.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../../src/widgets/luma_icon.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _totp = TextEditingController();
  bool _busy = false;
  bool _awaitingTotp = false;
  String? _error;

  Future<void> _submit() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    final result = await context.read<AuthService>().login(
          _email.text.trim(),
          _password.text,
          totpCode: _awaitingTotp ? _totp.text.trim() : null,
        );
    if (!mounted) return;
    setState(() {
      _busy = false;
      switch (result) {
        case LoginResult.success:
          // go_router redirect will navigate.
          break;
        case LoginResult.totpRequired:
          _awaitingTotp = true;
          _error = null;
          break;
        case LoginResult.invalidTotp:
          _awaitingTotp = true;
          _error = 'Invalid two-factor code.';
          _totp.clear();
          break;
        case LoginResult.badCredentials:
          _error = 'Invalid credentials.';
          _awaitingTotp = false;
          break;
        case LoginResult.networkError:
          _error = 'Network error — try again.';
          break;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 360),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: const [
                    LumaIcon(PhosphorIconsDuotone.headset, color: kPrimary, size: 32),
                    SizedBox(width: 10),
                    Flexible(
                      child: Text(
                        'Luma Tech Solutions',
                        style: TextStyle(fontSize: 20, fontWeight: FontWeight.w600),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 24),
                if (!_awaitingTotp) ...[
                  TextField(
                    controller: _email,
                    keyboardType: TextInputType.emailAddress,
                    decoration: const InputDecoration(labelText: 'Email'),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _password,
                    obscureText: true,
                    decoration: const InputDecoration(labelText: 'Password'),
                    onSubmitted: (_) => _busy ? null : _submit(),
                  ),
                ] else ...[
                  const Text(
                    'Two-factor verification',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Enter the 6-digit code from your authenticator app.',
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: _totp,
                    keyboardType: TextInputType.number,
                    autofocus: true,
                    decoration: const InputDecoration(labelText: 'Code'),
                    onSubmitted: (_) => _busy ? null : _submit(),
                  ),
                ],
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  Text(_error!, style: const TextStyle(color: Colors.redAccent)),
                ],
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: _busy ? null : _submit,
                  child: _busy
                      ? const SizedBox(
                          width: 18, height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2))
                      : Text(_awaitingTotp ? 'Verify' : 'Sign in'),
                ),
                if (_awaitingTotp) ...[
                  const SizedBox(height: 8),
                  TextButton(
                    onPressed: _busy
                        ? null
                        : () => setState(() {
                              _awaitingTotp = false;
                              _totp.clear();
                              _error = null;
                            }),
                    child: const Text('Back'),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
