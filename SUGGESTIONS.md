# Improvement suggestions

Findings from a full codebase review (June 2026). The highest-impact
items were implemented at the time of the review — upload validation,
DB indexes, SQL-side session/SLA queries, webhook rate limiting, the
Apple-inspired portal refresh, and the iOS-flavoured mobile reskin.
Everything below was deliberately deferred; each entry notes why it's
worth doing and where it would land.

## Security & robustness

- **Webhook HMAC signatures** — `tickets/inbound_webhook.py` now has
  rate limiting + a body cap, but callers that support it (GitHub,
  Stripe-style) could sign payloads. Add an optional `secret` on
  `IngestEndpoint` and verify `X-Signature` when set.
- **Content-Security-Policy + security headers** — the portal inlines
  its JS in `templates/base.html`, so adopting CSP means moving those
  scripts to static files first. `django-csp` + `Permissions-Policy`
  would round out the existing HSTS/secure-cookie hardening.
- **Attachment antivirus / content sniffing** — `luma_support/uploads.py`
  validates size + extension; pairing it with `python-magic` MIME
  sniffing (or ClamAV via Celery) would catch renamed executables.
- **Xero token refresh atomicity** — `billing/models.py` enforces a
  singleton `XeroConnection`, but two concurrent refreshes can race.
  Wrap refresh in `select_for_update()`.
- **`OutstandingToken` pruning** — expired JWT rows accumulate forever.
  Add a weekly beat task (or host cron) running
  `manage.py flushexpiredtokens`.

## Performance & code quality

- **`ClientDetailView` ticket pagination** — `luma_support/portal_views.py`
  hardcodes `[:50]` tickets on the client page; paginate or add a
  "view all" link into the filtered ticket list.
- **Redis page-fragment caching** — a default cache backend now exists
  (`CACHES` in settings). The dashboard, revenue dashboard, and SLA
  analytics pages re-aggregate on every hit and are natural candidates
  for 60s fragment caching.
- **Pre-existing flaky test** — `billing/test_metrics.py::
  test_gross_churn_rate_returns_fraction` fails on dates where its two
  generated contract invoices land in the same period (UNIQUE
  constraint). Make the test pin distinct `period_start` values.
- **Mobile list pagination** — repositories load full result sets;
  the DRF endpoints already paginate (PAGE_SIZE=25), so the mobile
  repositories silently truncate at page one. Add `page`/`next`
  handling to `TicketsRepository.list()` and friends, with
  infinite-scroll in the list screens.
- **Mobile search debouncing + skeleton loaders** — filter changes
  re-fire futures immediately and every screen shows a bare spinner;
  a 300ms debounce + shimmer placeholders would improve perceived
  speed.
- **`StatefulShellRoute` for tab state** — both shells note this TODO:
  tab taps are fresh navigations, losing scroll position. go_router's
  `StatefulShellRoute.indexedStack` preserves per-tab state.

## Features

- **Recurring billing schedule UI** — `billing/tasks.py::
  generate_contract_invoices` runs monthly with hardcoded behaviour.
  A `BillingSchedule` model (client, frequency, day-of-month) plus a
  portal/mobile settings page would let Marco vary cadence per client.
- **Quote expiry automation** — `Quote.valid_until` and `is_expired`
  exist but nothing acts on them. Add a beat task to auto-mark EXPIRED
  and email a reminder N days before.
- **Cmd-K search across leads + quotes** — `/api/v1/search/` covers
  tickets/clients/KB only. Leads and quotes have searchable fields and
  the palette UI needs no changes beyond new result types.
- **Client CSV bulk-import** — onboarding a business client means
  hand-creating systems + contacts. `POST /api/v1/clients/bulk-import/`
  accepting a validated CSV would cut that to minutes.
- **Time-vs-SLA analytics endpoint** — time entries and SLA deadlines
  exist; an aggregation endpoint (hours by client/tier/month, overrun
  tickets, billable %) would power a profitability-style report that
  already has a natural home next to `billing/profitability`.
- **SLA history / trend model** — SLA shifts (pauses, escalations)
  aren't logged, so "are we getting faster?" can't be answered. A small
  `SlaEvent` table written from `Ticket.save()` would enable trend
  charts on the SLA analytics page.
- **Kanban drag-and-drop** — the board (`ticket_board.html`) moves
  cards via a select dropdown; the native HTML Drag API posting to the
  existing status endpoint would make it feel right.
- **Mobile offline cache** — repositories could write last-known JSON
  to disk and serve it when offline (read-only), which matters for
  site visits in basements with no signal.
- **Web light mode** — the portal is dark-only by design today; the
  CSS custom properties make a `prefers-color-scheme` light variant a
  contained change to `static/css/app.css` if ever wanted.
- **`CupertinoPicker` quiet hours** — the quiet-hours sheet still uses
  dropdowns; an iOS wheel picker would finish the Apple feel there.
- **Replace `phosphor_flutter`** — the icon pack is a fork pinned at
  2.1.0; if it stalls against future Flutter releases, SF-Symbols-like
  alternatives (`cupertino_icons` full set, `lucide_icons`) are the
  natural swap.
- **Clear remaining Flutter info-level lints** — `flutter analyze` on
  current stable reports ~48 info diagnostics (mostly `withOpacity` →
  `withValues`, `DropdownButtonFormField.value` → `initialValue`,
  `prefer_const_constructors`, and a few `use_build_context_synchronously`
  guards). CI passes with `--no-fatal-infos`; a mechanical sweep would
  let us drop that flag.
