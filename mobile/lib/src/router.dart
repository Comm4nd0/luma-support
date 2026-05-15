import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import 'screens/client_dashboard_screen.dart';
import 'screens/client_detail_screen.dart';
import 'screens/engineer_dashboard_screen.dart';
import 'screens/kb_detail_screen.dart';
import 'screens/kb_list_screen.dart';
import 'screens/login_screen.dart';
import 'screens/notifications_inbox_screen.dart';
import 'screens/profile_screen.dart';
import 'screens/shells/client_shell.dart';
import 'screens/shells/engineer_shell.dart';
import 'screens/ticket_create_screen.dart';
import 'screens/ticket_detail_screen.dart';
import 'screens/ticket_list_screen.dart';
import 'services/auth_service.dart';
import 'services/current_user.dart';

/// Build the app's [GoRouter].
///
/// - `redirect` enforces auth: unauthenticated → /login; authenticated on
///   /login → /.
/// - The root path `/` chooses between the engineer and client shells
///   based on the cached [CurrentUser] role. While `/me` is in-flight a
///   bare scaffold is shown.
/// - Each shell is a [StatefulShellRoute] so its bottom-nav tabs preserve
///   state across switches.
GoRouter buildAppRouter({
  required AuthService auth,
  required CurrentUser currentUser,
}) {
  return GoRouter(
    initialLocation: '/',
    refreshListenable: Listenable.merge([auth, currentUser]),
    redirect: (context, state) {
      final loggedIn = auth.isAuthenticated;
      final loggingIn = state.matchedLocation == '/login';
      if (!loggedIn) {
        return loggingIn ? null : '/login';
      }
      if (loggingIn) return '/';
      return null;
    },
    routes: [
      GoRoute(
        path: '/login',
        builder: (_, __) => const LoginScreen(),
      ),
      GoRoute(
        path: '/',
        builder: (context, state) {
          final user = context.watch<CurrentUser>();
          if (user.loading || user.user == null) {
            return const Scaffold(
              body: Center(child: CircularProgressIndicator()),
            );
          }
          return user.isClient
              ? const ClientShell(child: ClientDashboardScreen())
              : const EngineerShell(child: EngineerDashboardScreen());
        },
      ),
      GoRoute(
        path: '/tickets',
        builder: (context, state) {
          final user = context.read<CurrentUser>();
          return user.isClient
              ? const ClientShell(child: TicketListScreen())
              : const EngineerShell(child: TicketListScreen());
        },
      ),
      GoRoute(
        path: '/tickets/new',
        builder: (_, __) => const TicketCreateScreen(),
      ),
      GoRoute(
        path: '/tickets/:id',
        builder: (_, state) => TicketDetailScreen(
          ticketId: int.parse(state.pathParameters['id']!),
        ),
      ),
      GoRoute(
        path: '/clients/:id',
        builder: (_, state) => ClientDetailScreen(
          clientId: int.parse(state.pathParameters['id']!),
        ),
      ),
      GoRoute(
        path: '/kb',
        builder: (context, state) {
          final user = context.read<CurrentUser>();
          return user.isClient
              ? const ClientShell(child: KbListScreen())
              : const EngineerShell(child: KbListScreen());
        },
      ),
      GoRoute(
        path: '/kb/:slug',
        builder: (_, state) => KbDetailScreen(slug: state.pathParameters['slug']!),
      ),
      GoRoute(
        path: '/notifications',
        builder: (context, state) {
          final user = context.read<CurrentUser>();
          return user.isClient
              ? const ClientShell(child: NotificationsInboxScreen())
              : const EngineerShell(child: NotificationsInboxScreen());
        },
      ),
      GoRoute(
        path: '/profile',
        builder: (context, state) {
          final user = context.read<CurrentUser>();
          return user.isClient
              ? const ClientShell(child: ProfileScreen())
              : const EngineerShell(child: ProfileScreen());
        },
      ),
    ],
  );
}
