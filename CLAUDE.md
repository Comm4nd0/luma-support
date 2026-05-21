# CLAUDE.md — luma-support

Notes for Claude when working in this repo.

## What this project is

Ticketing + client management for **Luma Tech Solutions**. Marco runs Luma
solo, so this is the day-to-day system of record: clients, the systems
they own (UniFi, home automation, websites, CCTV, …), tickets with SLAs,
time tracking, billing (Xero + Stripe), social-account management, a
small KB, leads + quotes pipeline, and a flag-driven feature dial.
There's a server-rendered web portal at `/` and a Flutter mobile app —
both must be at feature parity (see "Web/mobile parity" below).

## Layout

- `luma_support/` — Django settings + URL roots, the Celery app, and the
  server-rendered portal views (`portal_views.py` + `portal_urls.py`).
- `accounts/` — custom `User` (email login, `role` discriminator, TOTP
  fields, quiet-hours, recovery codes). Auth goes through djoser +
  SimpleJWT under `/api/v1/auth/`. Active-session list / revoke API
  lives here too.
- `audit/` — durable `AuditLog` for sensitive actions (Xero
  connect/disconnect, invoice push, credential access). `audit.log()`
  swallows its own exceptions so audit writes never break the caller.
- `billing/` — `Invoice`, `InvoiceLine`, `Payment`, `CreditNote`,
  `XeroConnection`. Pushes invoices to Xero, mirrors Xero payments,
  creates Stripe Payment Links via `billing/stripe_client.py`. Stripe
  webhook at `/api/v1/billing/webhooks/stripe/` is signature-verified.
  Quarterly VAT report + per-client profitability report.
- `clients/` — `Client`, `Contact`, `System`, plus per-client document
  library, onboarding-checklist progress, GDPR export + right-to-be-
  forgotten, GPS-bounded site-visit check-in/check-out, public per-
  client status pages (opt-in), one-click referral sharing.
  `System.credentials_encrypted` is Fernet-encrypted via
  `clients/encryption.py` (supports `FERNET_KEYS` rotation via
  MultiFernet + `manage.py rotate_fernet_keys`).
- `features/` — `FeatureFlag` model + `is_enabled(name, user=...)`.
  Master switch + percentage rollout (deterministic per user id) +
  allowed-users override. Defaults to OFF when the row is missing.
- `knowledge/` — Markdown KB articles with inline image / asset
  uploads. `client_visible=True` makes them appear to client users.
  `knowledge/ai.py` returns Claude-ranked article suggestions, falling
  back to keyword search when `ANTHROPIC_API_KEY` is empty.
- `leads/` — inbound lead capture + nurture pipeline.
- `notifications/` — in-app `Notification`, FCM push, and Celery tasks:
  `send_ticket_update_email`, `send_csat_email`, `check_sla_warnings`
  (5-min beat), `send_push`, Friday weekly client digest.
- `quotes/` — quote builder + PDF rendering + acceptance workflow.
- `social/` — LinkedIn / Facebook / Instagram inbox + scheduled posts
  + KPI dashboards. Refresh tasks run every 20 min.
- `system/` — `/system/health/` and `/system/readyz/` probes, plus
  `system/integrations/unifi.py` + the `refresh_unifi_devices` Celery
  task (every 30 min) that populates `System.devices_json` and
  `System.health_status`. Time-series anomaly detection on monitored
  systems.
- `tickets/` — `Ticket`, `TimeEntry`, `Attachment`, `TicketNote`,
  `CsatResponse`, `MaintenanceSchedule`, `SavedTicketFilter`,
  read-receipts. `tickets/ai.py` drafts engineer replies and inbox-zero
  suggestions via Claude. `tickets/inbound.py` turns inbound IMAP mail
  into Tickets / TicketNotes via plus-addressing. Kanban board view +
  saved filters with pinned-tab UX. PDF monthly reports via
  `tickets/reports.py` (ReportLab). Time-tracking analytics endpoint.
- `templates/portal/` — dark-themed Django templates for the web portal.
  Includes a Cmd/Ctrl-K command palette, vim-style keyboard shortcuts,
  and a print-friendly stylesheet for invoices.
- `mobile/` — Flutter app (engineer + client roles via role-aware
  shells; full feature parity with the portal — see below). Biometric
  app lock, FCM push, signature capture, GPS check-in.
- `scripts/` — backup_media.sh, backup_offsite.sh, test_restore.sh.
  Drive the layered backup system documented in `docs/BACKUPS.md`.
- `docs/` — `BACKUPS.md` (full backup + restore runbook).
- `deploy.py` — one-shot Hetzner deploy: git pull → docker build →
  migrate → up -d → tail logs.

## Web/mobile parity

**Any user-facing feature added to the web portal must also be added to
the mobile app, and vice versa.** Treat them as two front-ends to the
same backend, not as a "web first, mobile later" split.

When adding a feature, plan touches across:
1. The Django model / serializer / view (or DRF endpoint).
2. The portal template + portal view.
3. The mobile Dart model (`mobile/lib/src/models/`).
4. The mobile repository (`mobile/lib/src/repositories/`).
5. The mobile screen (`mobile/lib/src/screens/`) and route in
   `mobile/lib/src/router.dart`.
6. Tests on both sides (`pytest` + `flutter test`).

If a feature is genuinely portal- or admin-only (e.g. Xero OAuth setup),
say so explicitly in the commit; otherwise default to building both.

## SLA policy

Anchored at ticket creation, by priority:
critical = 2h, high = 4h, medium = 24h, low = 48h.
When `priority` isn't supplied, it auto-derives from the client's care
plan tier (see `tickets/sla.py:CARE_PLAN_PRIORITY`).

## Conventions

- Email is the username. Don't reintroduce `username`.
- Don't leak `credentials_encrypted` in responses — `SystemSerializer`
  treats `credentials` as write-only and encrypts on save.
- New features go via apps, not into `luma_support/`. Keep the project
  package thin.
- Tests use `pytest` + `pytest-django`. Run `pytest`.
- Conventional Commits.

## Things to remember

- Settings fall back to SQLite when `POSTGRES_HOST` is unset, so local
  `pytest` works without Docker.
- `FERNET_KEY` / `FERNET_KEYS` in `.env.example` are placeholders — the
  developer must generate real ones before storing real credentials.
  `FERNET_KEYS` (comma-separated) is preferred and enables rotation.
- The web portal is served at `/` (templates), the API at `/api/v1/`,
  admin at `/admin/`. Don't collide namespaces.
- Marco's brand colors: navy `#0f172a` background, teal `#14b8a6`
  primary. Defined in `static/css/app.css` and `mobile/lib/src/theme.dart`.
- 2FA: staff (admin + engineer) are forced into TOTP enrolment on
  first login. Client users skip TOTP. Mobile auth flow speaks the
  same `/api/v1/auth/jwt/create/` endpoint — see "Web/mobile parity".
- Optional integrations gate on env vars and no-op when empty:
  `STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET`, `ANTHROPIC_API_KEY`,
  `INBOUND_IMAP_HOST`, `FCM_ENABLED`, `SENTRY_DSN`, the LinkedIn / Meta
  client ids, and UniFi via `System.monitoring_url` + JSON-encoded
  `System.credentials_encrypted`. Add new integrations the same way so
  dev/CI don't reach external services.
- **Error reporting**: `SENTRY_DSN` wires up sentry-sdk's Django + Celery
  + logging integrations. Settings.py has a `before_send` scrubber that
  redacts secret-shaped headers / cookies / extras. Set
  `SENTRY_TRACES_SAMPLE_RATE > 0` to opt into performance traces.
- **Backups**: `pg_backup` service in docker-compose writes daily dumps
  to a separate `pg_backups` volume (7d / 4w / 12m rotation). Host
  crons drive `backup_media.sh` (tar.gz of media/), `backup_offsite.sh`
  (rsync to Hetzner Storage Box), and `test_restore.sh` (weekly drill).
  Full runbook in `docs/BACKUPS.md`. Off-site target gates on env vars
  so the cron is safe to install before the Storage Box exists.
- Deploy: `./deploy.py` on the Hetzner host. Runs git pull → docker
  build → explicit migrate against the new image → `up -d`. Aborts
  cleanly if migrate fails (old container keeps serving). Production
  runs on Luma001 (178.104.29.66), web on host port **8006** (proxied by
  Caddy as `support.lumatechsolutions.co.uk`).
- **Xcode Cloud**: pushing to `master` (or `main`) automatically
  triggers an iOS build in Xcode Cloud. The CI script is at
  `mobile/ios/ci_scripts/ci_post_clone.sh`. Be aware that any push
  to the default branch will kick off a build.
