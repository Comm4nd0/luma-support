import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

/// Bottom-nav scaffold shown to client-role users. Same pattern as
/// [EngineerShell] but with the tabs a customer needs: their tickets,
/// the knowledge base, alerts, and profile.
class ClientShell extends StatelessWidget {
  const ClientShell({super.key, required this.child});

  final Widget child;

  static const _destinations = <_NavDest>[
    _NavDest('/', Icons.home_outlined, Icons.home, 'Home'),
    _NavDest('/tickets', Icons.support_agent_outlined, Icons.support_agent,
        'My tickets'),
    _NavDest('/kb', Icons.menu_book_outlined, Icons.menu_book, 'Knowledge'),
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
