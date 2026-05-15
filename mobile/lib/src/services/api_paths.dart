// Centralised API path constants.
//
// Django mounts each app under /api/v1/<app>/ and each DRF router then
// registers its viewset under a basename — that double-prefix is the
// source of the old `tickets/` vs `tickets/tickets/` bug. Routing every
// HTTP call through this file means a path can never drift again.

class ApiPaths {
  ApiPaths._();

  // Auth (djoser + SimpleJWT)
  static const String login = '/auth/jwt/create/';
  static const String refresh = '/auth/jwt/refresh/';
  static const String me = '/auth/users/me/';

  // Tickets
  static const String tickets = '/tickets/tickets/';
  static String ticket(int id) => '/tickets/tickets/$id/';
  static String ticketStatus(int id) => '/tickets/tickets/$id/status/';
  static String ticketTime(int id) => '/tickets/tickets/$id/time/';
  static String ticketNotes(int id) => '/tickets/tickets/$id/notes/';
  static String ticketAttachments(int id) =>
      '/tickets/tickets/$id/attachments/';
  static const String slaWarnings = '/tickets/tickets/sla-warnings/';
  static const String timeEntries = '/tickets/time-entries/';

  // Clients / Systems / Contacts
  static const String clients = '/clients/clients/';
  static String client(int id) => '/clients/clients/$id/';
  static const String systems = '/clients/systems/';
  static const String contacts = '/clients/contacts/';

  // Knowledge
  static const String articles = '/knowledge/articles/';
  static String article(String slug) => '/knowledge/articles/$slug/';
  static const String articleSearch = '/knowledge/articles/search/';

  // Billing (admin-only on the server)
  static const String invoices = '/billing/invoices/';
  static String invoice(int id) => '/billing/invoices/$id/';
  static String invoiceSend(int id) => '/billing/invoices/$id/send/';
  static String invoiceStatus(int id) => '/billing/invoices/$id/status/';
  static const String invoicesGenerateFromTime =
      '/billing/invoices/generate-from-time/';
  static const String payments = '/billing/payments/';
  static String payment(int id) => '/billing/payments/$id/';

  // Notifications + devices
  static const String notifications = '/notifications/notifications/';
  static String notification(int id) => '/notifications/notifications/$id/';
  static String notificationMarkRead(int id) =>
      '/notifications/notifications/$id/mark-read/';
  static const String notificationsMarkAllRead =
      '/notifications/notifications/mark-all-read/';
  static const String notificationsUnreadCount =
      '/notifications/notifications/unread_count/';
  static const String devices = '/notifications/devices/';
  static String device(int id) => '/notifications/devices/$id/';
}
