import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

/// Bottom-nav scaffold shown to admin/engineer roles. The four tabs map
/// to top-level routes; we don't use [StatefulShellRoute] so each tap is
/// a fresh navigation — that's fine for an MVP, swap in later if state
/// preservation across tabs becomes important.
class EngineerShell extends StatelessWidget {
  const EngineerShell({super.key, required this.child});

  final Widget child;

  static const _destinations = <_NavDest>[
    _NavDest('/', Icons.dashboard_outlined, Icons.dashboard, 'Home'),
    _NavDest('/tickets', Icons.confirmation_number_outlined,
        Icons.confirmation_number, 'Tickets'),
    _NavDest('/notifications', Icons.notifications_outlined,
        Icons.notifications, 'Alerts'),
    _NavDest('/profile', Icons.person_outline, Icons.person, 'Profile'),
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
              icon: Icon(d.icon),
              selectedIcon: Icon(d.selectedIcon),
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
