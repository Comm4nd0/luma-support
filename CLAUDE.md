# CLAUDE.md — luma-support

Notes for Claude when working in this repo.

## What this project is

Ticketing + client management for **Luma Tech Solutions**. Marco runs Luma
solo, so this is the day-to-day system of record: clients, the systems
they own (UniFi, home automation, websites, CCTV, …), tickets with SLAs,
time tracking, and a small KB.

## Layout

- `luma_support/` — Django settings + URL roots, the Celery app, and the
  server-rendered portal views (`portal_views.py` + `portal_urls.py`).
- `accounts/` — custom `User` (email login, `role` discriminator). Auth
  goes through djoser + SimpleJWT under `/api/v1/auth/`.
- `clients/` — `Client` and `System`. `System.credentials_encrypted` is
  Fernet-encrypted via `clients/encryption.py`.
- `tickets/` — `Ticket`, `TimeEntry`, `Attachment`, `TicketNote`. SLA
  policy lives in `tickets/sla.py`. Status transitions go through
  `Ticket.transition_to()` so the resolved/closed timestamps stay
  consistent. A `pre_save` signal captures the old status; a `post_save`
  signal queues a Celery email.
- `knowledge/` — Markdown KB articles. `client_visible=True` makes them
  appear to client users.
- `notifications/` — in-app `Notification` model + two Celery tasks:
  `send_ticket_update_email` (called from the ticket signal) and
  `check_sla_warnings` (Celery beat, every 5 minutes).
- `system/` — `/system/health/` and `/system/readyz/` probes.
- `templates/portal/` — dark-themed Django templates for the web portal.
- `mobile/` — Flutter app (login, ticket list/detail/create).

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
- `FERNET_KEY` in `.env.example` is a placeholder — the developer is
  expected to generate a real one before storing real credentials.
- The web portal is served at `/` (templates), the API at `/api/v1/`,
  admin at `/admin/`. Don't collide namespaces.
- Marco's brand colors: navy `#0f172a` background, teal `#14b8a6`
  primary. Defined in `static/css/app.css` and `mobile/lib/src/theme.dart`.
