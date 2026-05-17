import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../services/auth_service.dart';
import '../services/current_user.dart';
import '../services/push_service.dart';
import 'widgets/luma_drawer.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../../src/widgets/luma_icon.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  static const _version = '0.1.0';

  @override
  Widget build(BuildContext context) {
    final user = context.watch<CurrentUser>().user;
    final isStaff = context.watch<CurrentUser>().isStaff;
    final auth = context.read<AuthService>();
    final pushToken = PushService.instance.token;
    return Scaffold(
      appBar: AppBar(title: const Text('Profile')),
      drawer: isStaff ? const LumaDrawer() : null,
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (user != null) ...[
            CircleAvatar(
              radius: 36,
              child: Text(
                user.displayName.isEmpty
                    ? '?'
                    : user.displayName[0].toUpperCase(),
                style: const TextStyle(fontSize: 28),
              ),
            ),
            const SizedBox(height: 12),
            Center(
              child: Text(
                user.displayName,
                style:
                    const TextStyle(fontSize: 20, fontWeight: FontWeight.w600),
              ),
            ),
            Center(child: Text(user.email)),
            const SizedBox(height: 8),
            Center(
              child: Chip(label: Text('Role: ${user.role.name}')),
            ),
            const SizedBox(height: 24),
          ] else
            const Center(child: CircularProgressIndicator()),
          if (user?.isAdmin ?? false)
            ListTile(
              leading: const LumaIcon(PhosphorIconsDuotone.receipt),
              title: const Text('Billing'),
              subtitle: const Text('Invoices and Xero sync'),
              trailing: const LumaIcon(PhosphorIconsDuotone.caretRight),
              onTap: () => context.push('/billing/invoices'),
            ),
          ListTile(
            leading: const LumaIcon(PhosphorIconsDuotone.bellRinging),
            title: const Text('Push notifications'),
            subtitle: Text(
              pushToken == null
                  ? 'Not yet registered. Reopen the app to enable.'
                  : 'Active on this device.',
            ),
          ),
          ListTile(
            leading: const LumaIcon(PhosphorIconsDuotone.info),
            title: const Text('App version'),
            subtitle: const Text(_version),
          ),
          const Divider(),
          ListTile(
            leading: const LumaIcon(PhosphorIconsDuotone.signOut, color: Colors.redAccent),
            title: const Text('Sign out',
                style: TextStyle(color: Colors.redAccent)),
            onTap: () async {
              await auth.logout();
              if (context.mounted) {
                context.read<CurrentUser>().clear();
              }
            },
          ),
        ],
      ),
    );
  }
}
