import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../../../src/widgets/luma_icon.dart';

/// Bottom-nav scaffold shown to client-role users. Same pattern as
/// [EngineerShell] but with the tabs a customer needs: their tickets,
/// the knowledge base, alerts, and profile.
class ClientShell extends StatelessWidget {
  const ClientShell({super.key, required this.child});

  final Widget child;

  static const _destinations = <_NavDest>[
    _NavDest('/', PhosphorIconsDuotone.house, PhosphorIconsDuotone.house, 'Home'),
    _NavDest('/tickets', PhosphorIconsDuotone.headset, PhosphorIconsDuotone.headset,
        'My tickets'),
    _NavDest('/kb', PhosphorIconsDuotone.bookOpen, PhosphorIconsDuotone.bookOpen, 'Knowledge'),
    _NavDest('/notifications', PhosphorIconsDuotone.bell,
        PhosphorIconsDuotone.bell, 'Alerts'),
    _NavDest('/profile', PhosphorIconsDuotone.user, PhosphorIconsDuotone.user, 'Profile'),
  ];

  @override
  Widget build(BuildContext context) {
    final location = GoRouterState.of(context).matchedLocation;
    final index = _indexFor(location);
    return Scaffold(
      body: child,
      bottomNavigationBar: NavigationBar(
        selectedIndex: index,
        onDestinationSelected: (i) => context.go(_destinations[i].route),
        destinations: [
          for (final d in _destinations)
            NavigationDestination(
              icon: LumaIcon(d.icon),
              selectedIcon: LumaIcon(d.selectedIcon),
              label: d.label,
            ),
        ],
      ),
    );
  }

  int _indexFor(String location) {
    for (var i = 0; i < _destinations.length; i++) {
      if (location == _destinations[i].route) return i;
    }
    return 0;
  }
}

class _NavDest {
  const _NavDest(this.route, this.icon, this.selectedIcon, this.label);
  final String route;
  final IconData icon;
  final IconData selectedIcon;
  final String label;
}
