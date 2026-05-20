import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import 'package:provider/provider.dart';

import '../../services/current_user.dart';
import '../../widgets/luma_icon.dart';

/// Side menu surfacing staff/admin destinations that are no longer on the
/// dashboard: Maintenance (staff), Billing (admin), Audit (admin), plus
/// Profile. Bottom-nav routes (Home/Tickets/Alerts/Profile) stay where
/// they are — this drawer is purely for the deeper destinations.
class LumaDrawer extends StatelessWidget {
  const LumaDrawer({super.key});

  @override
  Widget build(BuildContext context) {
    final user = context.watch<CurrentUser>().user;
    final isAdmin = context.watch<CurrentUser>().isAdmin;
    final isStaff = context.watch<CurrentUser>().isStaff;

    void go(String path) {
      Navigator.of(context).pop();
      context.push(path);
    }

    return Drawer(
      child: SafeArea(
        child: ListView(
          padding: EdgeInsets.zero,
          children: [
            if (user != null)
              UserAccountsDrawerHeader(
                accountName: Text(
                  user.displayName.isEmpty ? user.email : user.displayName,
                ),
                accountEmail: Text(user.email),
                currentAccountPicture: CircleAvatar(
                  child: Text(
                    (user.displayName.isEmpty ? user.email : user.displayName)
                        .substring(0, 1)
                        .toUpperCase(),
                  ),
                ),
              ),
            if (isStaff)
              ListTile(
                leading: const LumaIcon(PhosphorIconsDuotone.funnel),
                title: const Text('Leads'),
                subtitle: const Text('Sales pipeline and follow-ups'),
                onTap: () => go('/leads'),
              ),
            if (isStaff)
              ListTile(
                leading: const LumaIcon(PhosphorIconsDuotone.fileText),
                title: const Text('Quotes'),
                subtitle: const Text('Proposals before invoicing'),
                onTap: () => go('/quotes'),
              ),
            if (isStaff)
              ListTile(
                leading: const LumaIcon(PhosphorIconsDuotone.calendar),
                title: const Text('Maintenance'),
                subtitle: const Text('Recurring work schedules'),
                onTap: () => go('/maintenance'),
              ),
            if (isStaff)
              ListTile(
                leading: const LumaIcon(PhosphorIconsDuotone.chatCircleDots),
                title: const Text('Social inbox'),
                subtitle: const Text('DMs, mentions and comments'),
                onTap: () => go('/social/inbox'),
              ),
            if (isAdmin)
              ListTile(
                leading: const LumaIcon(PhosphorIconsDuotone.receipt),
                title: const Text('Billing'),
                subtitle: const Text('Invoices and Xero sync'),
                onTap: () => go('/billing/invoices'),
              ),
            if (isAdmin)
              ListTile(
                leading: const LumaIcon(PhosphorIconsDuotone.chartLineUp),
                title: const Text('Revenue'),
                subtitle: const Text('MRR, ARR, churn'),
                onTap: () => go('/revenue'),
              ),
            if (isAdmin)
              ListTile(
                leading: const LumaIcon(PhosphorIconsDuotone.shieldCheck),
                title: const Text('Audit log'),
                subtitle: const Text('Credential + billing actions'),
                onTap: () => go('/audit'),
              ),
            const Divider(),
            ListTile(
              leading: const LumaIcon(PhosphorIconsDuotone.user),
              title: const Text('Profile'),
              onTap: () => go('/profile'),
            ),
          ],
        ),
      ),
    );
  }
}
