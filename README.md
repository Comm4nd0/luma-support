# Luma Tech Solutions

Ticketing and client management system for **Luma Tech Solutions**.

Backend: Django 5 + DRF + Channels (Daphne) + Celery, Postgres, Redis.
Mobile: Flutter (engineers + clients).

The web portal is themed to match
[lumatechsolutions.co.uk](https://lumatechsolutions.co.uk) — navy `#0f172a`
with teal `#14b8a6` accents.

## What's in here

| Path                | What it does                                        |
| ------------------- | --------------------------------------------------- |
| `accounts/`         | Custom `User` (email login, role discriminator), djoser+JWT auth |
| `clients/`          | `Client` and `System` (with Fernet-encrypted credentials) |
| `tickets/`          | `Ticket`, `TimeEntry`, `Attachment`, `TicketNote`, SLA logic |
| `knowledge/`        | Markdown KB articles (admin-authored, optional client-visible) |
| `notifications/`    | In-app notifications + Celery email tasks + 5-min SLA sweep |
| `system/`           | `/system/health/` and `/system/readyz/` probes      |
| `templates/portal/` | Server-rendered web portal (dark theme)             |
| `mobile/`           | Flutter app (login, ticket list/detail/create)      |

## Quick start (Docker)

```bash
cp .env.example .env
# Generate a Fernet key and paste it into FERNET_KEY:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

docker compose up --build -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_demo
docker compose exec web python manage.py createsuperuser
```

The portal is at <http://localhost:8006/>.
The API is at <http://localhost:8006/api/v1/>.

### Demo logins (after `seed_demo`)

- `marco@lumatechsolutions.co.uk` / `luma_admin_password` (admin)
- `engineer@lumatechsolutions.co.uk` / `luma_engineer_password` (engineer)

## Quick start (local Python)

```bash
python -m venv .venv && source .venv/bin/activate     # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
# Leave POSTGRES_HOST blank in .env to fall back to SQLite for local dev.
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 8006
```

## Tests

```bash
pytest
```

## API

| Endpoint                                      | Description                          |
| --------------------------------------------- | ------------------------------------ |
| `POST /api/v1/auth/jwt/create/`               | Obtain JWT pair                      |
| `POST /api/v1/auth/jwt/refresh/`              | Refresh access token                 |
| `GET  /api/v1/clients/`                       | List clients                         |
| `GET  /api/v1/tickets/`                       | List tickets (sorted by SLA)         |
| `POST /api/v1/tickets/{id}/status/`           | Transition status                    |
| `POST /api/v1/tickets/{id}/time/`             | Log time                             |
| `POST /api/v1/tickets/{id}/notes/`            | Add note (set `internal: true/false`)|
| `POST /api/v1/tickets/{id}/attachments/`      | Upload attachment (multipart)        |
| `GET  /api/v1/tickets/sla-warnings/`          | Tickets approaching / past SLA       |
| `GET  /api/v1/notifications/`                 | Current user's notifications         |
| `POST /api/v1/notifications/{id}/mark-read/`  | Mark single notification read        |

## SLA policy

Auto-priority is derived from the client's care plan tier when the caller
doesn't pass `priority`. Deadlines are anchored at ticket creation:

| Priority | Response target |
| -------- | --------------- |
| critical | 2 hours         |
| high     | 4 hours         |
| medium   | 24 hours        |
| low      | 48 hours        |

A Celery beat job runs every 5 minutes and creates `SLA_WARNING` notifications
for any open ticket within 30 minutes of breach (or already breached).

## Mobile app

See [`mobile/README.md`](mobile/README.md). Push notifications require
running `flutterfire configure` and dropping in the Firebase config files.

## Repo conventions

- Conventional Commits.
- Black + isort formatting (informal — no pre-commit yet).
- pytest for backend; `flutter test` for mobile.
