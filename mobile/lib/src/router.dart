import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import 'screens/client_dashboard_screen.dart';
import 'screens/client_detail_screen.dart';
import 'screens/client_form_screen.dart';
import 'screens/client_list_screen.dart';
import 'screens/engineer_dashboard_screen.dart';
import 'screens/invoice_create_screen.dart';
import 'screens/invoice_detail_screen.dart';
import 'screens/invoice_list_screen.dart';
import 'screens/kb_detail_screen.dart';
import 'screens/kb_list_screen.dart';
import 'screens/audit_log_screen.dart';
import 'screens/lead_detail_screen.dart';
import 'screens/lead_form_screen.dart';
import 'screens/lead_list_screen.dart';
import 'screens/login_screen.dart';
import 'screens/quote_detail_screen.dart';
import 'screens/quote_list_screen.dart';
import 'screens/refer_screen.dart';
import 'screens/maintenance_form_screen.dart';
import 'screens/maintenance_list_screen.dart';
import 'models/client.dart';
import 'models/lead.dart';
import 'models/maintenance_schedule.dart';
import 'screens/my_services_screen.dart';
import 'screens/notifications_inbox_screen.dart';
import 'screens/payments_screen.dart';
import 'screens/profile_screen.dart';
import 'screens/shells/client_shell.dart';
import 'screens/shells/engineer_shell.dart';
import 'screens/social_inbox_screen.dart';
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
      // Billing endpoints are admin-only on the server; redirect anyone
      // else away rather than letting the screen 401.
      if (state.matchedLocation.startsWith('/billing') &&
          !currentUser.isAdmin) {
        return '/';
      }
      // Audit feed is admin-only, maintenance is staff-only.
      if (state.matchedLocation.startsWith('/audit') &&
          !currentUser.isAdmin) {
        return '/';
      }
      if (state.matchedLocation.startsWith('/maintenance') &&
          currentUser.isClient) {
        return '/';
      }
      if (state.matchedLocation.startsWith('/leads') &&
          currentUser.isClient) {
        return '/';
      }
      if (state.matchedLocation.startsWith('/quotes') &&
          currentUser.isClient) {
        return '/';
      }
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
        path: '/clients',
        builder: (context, state) {
          final user = context.read<CurrentUser>();
          return user.isClient
              ? const ClientShell(child: ClientListScreen())
              : const EngineerShell(child: ClientListScreen());
        },
      ),
      GoRoute(
        path: '/clients/new',
        builder: (_, __) => const ClientFormScreen(),
      ),
      GoRoute(
        path: '/clients/:id',
        builder: (_, state) => ClientDetailScreen(
          clientId: int.parse(state.pathParameters['id']!),
        ),
      ),
      GoRoute(
        path: '/clients/:id/edit',
        builder: (_, state) {
          final extra = state.extra;
          if (extra is Client) {
            return ClientFormScreen(client: extra);
          }
          return ClientEditLoader(
            clientId: int.parse(state.pathParameters['id']!),
          );
        },
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
        path: '/billing',
        redirect: (_, __) => '/billing/invoices',
      ),
      GoRoute(
        path: '/billing/invoices',
        builder: (context, state) =>
            const EngineerShell(child: InvoiceListScreen()),
      ),
      GoRoute(
        path: '/billing/invoices/new',
        builder: (_, __) => const InvoiceCreateScreen(),
      ),
      GoRoute(
        path: '/billing/invoices/:id',
        builder: (_, state) => InvoiceDetailScreen(
          invoiceId: int.parse(state.pathParameters['id']!),
        ),
      ),
      GoRoute(
        path: '/billing/payments',
        builder: (_, __) => const PaymentsScreen(),
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
      GoRoute(
        path: '/my-services',
        builder: (context, state) {
          final user = context.read<CurrentUser>();
          return user.isClient
              ? const ClientShell(child: MyServicesScreen())
              : const EngineerShell(child: MyServicesScreen());
        },
      ),
      GoRoute(
        path: '/maintenance',
        builder: (_, __) =>
            const EngineerShell(child: MaintenanceListScreen()),
      ),
      GoRoute(
        path: '/maintenance/new',
        builder: (_, __) => const MaintenanceFormScreen(),
      ),
      GoRoute(
        path: '/maintenance/:id/edit',
        builder: (_, state) => MaintenanceFormScreen(
          schedule: state.extra as MaintenanceSchedule?,
        ),
      ),
      GoRoute(
        path: '/audit',
        builder: (_, __) =>
            const EngineerShell(child: AuditLogScreen()),
      ),
      GoRoute(
        path: '/social/inbox',
        builder: (_, __) =>
            const EngineerShell(child: SocialInboxScreen()),
      ),
      GoRoute(
        path: '/leads',
        builder: (_, __) => const EngineerShell(child: LeadListScreen()),
      ),
      GoRoute(
        path: '/leads/new',
        builder: (_, __) => const LeadFormScreen(),
      ),
      GoRoute(
        path: '/leads/:id',
        builder: (_, state) => LeadDetailScreen(
          leadId: int.parse(state.pathParameters['id']!),
        ),
      ),
      GoRoute(
        path: '/leads/:id/edit',
        builder: (_, state) {
          final extra = state.extra;
          if (extra is Lead) {
            return LeadFormScreen(lead: extra);
          }
          return LeadEditLoader(
            leadId: int.parse(state.pathParameters['id']!),
          );
        },
      ),
      GoRoute(
        path: '/quotes',
        builder: (_, __) => const EngineerShell(child: QuoteListScreen()),
      ),
      GoRoute(
        path: '/quotes/:id',
        builder: (_, state) => QuoteDetailScreen(
          quoteId: int.parse(state.pathParameters['id']!),
        ),
      ),
      GoRoute(
        path: '/refer',
        builder: (context, state) {
          final user = context.read<CurrentUser>();
          return user.isClient
              ? const ClientShell(child: ReferScreen())
              : const EngineerShell(child: ReferScreen());
        },
      ),
    ],
  );
}
