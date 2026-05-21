import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../services/app_lock_service.dart';
import '../../theme.dart';

/// Wraps every router page; renders the lock overlay when the lock
/// service says we're locked.
///
/// Use this through [MaterialApp.router]'s ``builder`` parameter so the
/// gate sits above every route (including ``/login``, so a fingerprint
/// dialog can't be skipped by deep-linking).
class AppLockGate extends StatelessWidget {
  const AppLockGate({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final lock = context.watch<AppLockService>();
    return Stack(
      children: [
        child,
        if (lock.locked) const _LockOverlay(),
      ],
    );
  }
}

class _LockOverlay extends StatefulWidget {
  const _LockOverlay();

  @override
  State<_LockOverlay> createState() => _LockOverlayState();
}

class _LockOverlayState extends State<_LockOverlay> {
  bool _autoPromptDone = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Auto-trigger the system biometric prompt once on lock; users can
    // re-prompt via the "Unlock" button if they cancel.
    if (!_autoPromptDone) {
      _autoPromptDone = true;
      WidgetsBinding.instance.addPostFrameCallback((_) => _prompt());
    }
  }

  Future<void> _prompt() async {
    final lock = context.read<AppLockService>();
    await lock.unlock();
  }

  @override
  Widget build(BuildContext context) {
    final lock = context.watch<AppLockService>();
    return Material(
      color: kBackground,
      child: SafeArea(
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.lock_outline, size: 64, color: kPrimary),
              const SizedBox(height: 12),
              const Text(
                'Luma Tech Solutions',
                style: TextStyle(
                  color: kText,
                  fontSize: 20,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 6),
              const Text(
                'Authenticate to continue',
                style: TextStyle(color: kMuted),
              ),
              const SizedBox(height: 24),
              ElevatedButton.icon(
                onPressed: lock.attempting ? null : _prompt,
                icon: const Icon(Icons.fingerprint),
                label: Text(lock.attempting ? 'Authenticating…' : 'Unlock'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
