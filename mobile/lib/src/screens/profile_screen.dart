import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../services/auth_service.dart';
import '../services/current_user.dart';
import '../services/push_service.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  static const _version = '0.1.0';

  @override
  Widget build(BuildContext context) {
    final user = context.watch<CurrentUser>().user;
    final auth = context.read<AuthService>();
    final pushToken = PushService.instance.token;
    return Scaffold(
      appBar: AppBar(title: const Text('Profile')),
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
          ListTile(
            leading: const Icon(Icons.notifications_active),
            title: const Text('Push notifications'),
            subtitle: Text(
              pushToken == null
                  ? 'Not yet registered. Reopen the app to enable.'
                  : 'Active on this device.',
            ),
          ),
          ListTile(
            leading: const Icon(Icons.info_outline),
            title: const Text('App version'),
            subtitle: const Text(_version),
          ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.logout, color: Colors.redAccent),
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
