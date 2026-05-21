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
  static const String recoveryCodes = '/auth/recovery-codes/';

  // Tickets
  static const String tickets = '/tickets/tickets/';
  static String ticket(int id) => '/tickets/tickets/$id/';
  static String ticketStatus(int id) => '/tickets/tickets/$id/status/';
  static String ticketTime(int id) => '/tickets/tickets/$id/time/';
  static String ticketNotes(int id) => '/tickets/tickets/$id/notes/';
  static String ticketAttachments(int id) =>
      '/tickets/tickets/$id/attachments/';
  static String ticketDraftReply(int id) =>
      '/tickets/tickets/$id/draft-reply/';
  static String ticketSummarise(int id) =>
      '/tickets/tickets/$id/summarise/';
  static String ticketMergeInto(int source, int target) =>
      '/tickets/tickets/$source/merge-into/$target/';
  static const String slaWarnings = '/tickets/tickets/sla-warnings/';
  static const String dashboardStats = '/tickets/tickets/dashboard-stats/';
  static const String ticketTags = '/tickets/ticket-tags/';
  static String ticketTag(int id) => '/tickets/ticket-tags/$id/';
  static const String ticketTemplates = '/tickets/ticket-templates/';
  static const String ticketsBulk = '/tickets/tickets/bulk/';
  static const String timeEntries = '/tickets/time-entries/';
  static const String maintenanceSchedules =
      '/tickets/maintenance-schedules/';
  static String maintenanceSchedule(int id) =>
      '/tickets/maintenance-schedules/$id/';

  // Clients / Systems / Contacts
  static const String clients = '/clients/clients/';
  static String client(int id) => '/clients/clients/$id/';
  static String clientHealth(int id) => '/clients/clients/$id/health/';
  static const String systems = '/clients/systems/';
  static const String contacts = '/clients/contacts/';
  static const String myReferralCode = '/clients/referral-code/';

  // Leads (staff-only — CRM pipeline before a Client exists)
  static const String leads = '/leads/leads/';
  static String lead(int id) => '/leads/leads/$id/';
  static String leadAdvance(int id) => '/leads/leads/$id/advance/';
  static String leadConvert(int id) => '/leads/leads/$id/convert/';
  static String leadActivities(int id) => '/leads/leads/$id/activities/';

  // Quotes (staff-only)
  static const String quotes = '/quotes/quotes/';
  static String quote(int id) => '/quotes/quotes/$id/';
  static String quoteSend(int id) => '/quotes/quotes/$id/send/';
  static String quoteAccept(int id) => '/quotes/quotes/$id/accept/';
  static String quoteReject(int id) => '/quotes/quotes/$id/reject/';

  // Knowledge
  static const String articles = '/knowledge/articles/';
  static String article(String slug) => '/knowledge/articles/$slug/';
  static const String articleSearch = '/knowledge/articles/search/';
  static const String articleSuggest = '/knowledge/articles/suggest/';

  // Audit (admin-only)
  static const String auditLogs = '/audit/logs/';

  // Billing (admin-only on the server)
  static const String invoices = '/billing/invoices/';
  static String invoice(int id) => '/billing/invoices/$id/';
  static String invoiceSend(int id) => '/billing/invoices/$id/send/';
  static String invoiceStatus(int id) => '/billing/invoices/$id/status/';
  static const String invoicesGenerateFromTime =
      '/billing/invoices/generate-from-time/';
  static const String payments = '/billing/payments/';
  static String payment(int id) => '/billing/payments/$id/';
  static const String revenueMetrics = '/billing/revenue/';
  static const String stripePortalSession = '/billing/portal-session/';

  // Social (Luma's own LinkedIn / FB Page / IG Business)
  static const String socialAccounts = '/social/accounts/';
  static const String socialInbox = '/social/inbox/';
  static String socialInboxDismiss(int id) => '/social/inbox/$id/dismiss/';
  static String socialInboxConvert(int id) =>
      '/social/inbox/$id/convert-to-ticket/';

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
