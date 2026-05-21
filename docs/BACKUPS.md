# Backups & restore — luma-support

How the database, uploaded media and audit-of-last-resort copies are
preserved. **Read this end-to-end before relying on the system in
production.**

## What's protected, by what

| Asset                         | Protected by                                 |
| ----------------------------- | -------------------------------------------- |
| Postgres database             | Daily `pg_dump` (rotation: 7d / 4w / 12m)    |
| `media/` (CVs, KB images, ticket attachments, client docs) | Daily tar.gz (7d rotation) |
| Off-site copy of both         | Daily rsync to Hetzner Storage Box (opt-in)  |
| Restore actually works        | Weekly automated restore drill               |

## Three layers

```
1.  postgres  ──daily──>  pg_backups volume     (on-box)
    media/    ──daily──>  pg_backups/media      (on-box)
2.  pg_backups ──daily──> Hetzner Storage Box   (off-box)  ← off-site
3.  weekly cron: spin throwaway pg, restore latest dump, run sanity queries
```

If layer 2 isn't configured, layer 1 still buys you protection against
accidental delete / bad migration. It does **not** protect you against
the Hetzner SSD dying. Configure layer 2.

## What runs in Docker Compose

The `pg_backup` service in `docker-compose.yml` uses
[`prodrigestivill/postgres-backup-local`][img] — an image that's been
running in real production for ~7 years. It writes to a separate volume
(`pg_backups`) so a disk-fill on the app side can't kill the backups.

[img]: https://github.com/prodrigestivill/docker-postgres-backup-local

```yaml
SCHEDULE: "@daily"        # cron expression, UTC
BACKUP_KEEP_DAYS:   7
BACKUP_KEEP_WEEKS:  4
BACKUP_KEEP_MONTHS: 12
```

Dump layout inside the volume:

```
/backups/
├── daily/    luma_support-2026-05-21.sql.gz, …
├── weekly/   luma_support-2026-W21.sql.gz, …
├── monthly/  luma_support-2026-05.sql.gz, …
└── last/     luma_support-latest.sql.gz   ← symlink to the freshest
```

## Cron — install on the Hetzner host

After `docker compose up -d --build`, install three host cron jobs.
**Run this on the server** (`crontab -e`):

```cron
# Daily — snapshot media/ into the pg_backups volume.
0 3 * * *  cd /root/luma-support && ./scripts/backup_media.sh >> /var/log/luma-media-backup.log 2>&1

# Daily — push everything off-site (no-op until env vars are set).
30 3 * * *  cd /root/luma-support && ./scripts/backup_offsite.sh >> /var/log/luma-offsite.log 2>&1

# Weekly — restore drill: prove the latest backup is still restorable.
0 4 * * 0  cd /root/luma-support && ./scripts/test_restore.sh >> /var/log/luma-restore-drill.log 2>&1
```

Postgres dumps themselves are driven by the container's own schedule —
no host cron needed for those.

## Off-site setup (Hetzner Storage Box example)

A Storage Box costs about €3.20/mo for 1 TB and is in a different
datacenter from your Hetzner Cloud server, so a single-DC outage doesn't
kill both. Setup:

1. Order a Storage Box from Hetzner Robot.
2. Generate a dedicated SSH key on the Luma001 server:
   ```sh
   ssh-keygen -t ed25519 -f ~/.ssh/luma_offsite -N ''
   ```
3. Upload the public key to the Storage Box (Hetzner Robot → Storage
   Box → SSH keys).
4. Add the env vars to `/root/.bashrc` or — preferably — `/etc/environment`:
   ```sh
   export LUMA_BACKUP_OFFSITE_HOST=u123456.your-storagebox.de
   export LUMA_BACKUP_OFFSITE_USER=u123456-sub1
   export LUMA_BACKUP_OFFSITE_PATH=/home/backups/luma-support
   ```
5. Test it once by hand:
   ```sh
   cd /root/luma-support && ./scripts/backup_offsite.sh
   ```

If you skip step 4, the script silently no-ops with exit 0 — so the cron
job in the previous section is safe to install before the Storage Box
exists.

## Restore drills

### Automated (weekly cron)

Spins up a throwaway Postgres, pipes in the latest dump, runs sanity
queries, throws everything away. Output goes to
`/var/log/luma-restore-drill.log`. **Check it after the first run.** If
the drill fails for two consecutive weeks, treat it as an incident.

### Manual (after a scary deploy)

```sh
cd /root/luma-support
./scripts/test_restore.sh
```

Exit codes:
- `0` — backup restored cleanly, sanity queries passed
- `1` — no backup found (compose stack not up, or pg_backup hasn't run yet)
- `2` — restore or sanity query failed (look at the output)

### Manual full recovery — "the database is gone"

```sh
cd /root/luma-support

# 1. Identify the dump you want to restore from.
docker compose run --rm pg_backup ls -la /backups/daily/
# pick e.g. luma_support-2026-05-21.sql.gz

# 2. Stop the apps (db must be idle).
docker compose stop web celery celery-beat

# 3. Drop and recreate the database.
docker compose exec postgres dropdb -U "$POSTGRES_USER" "$POSTGRES_DB" --if-exists
docker compose exec postgres createdb -U "$POSTGRES_USER" "$POSTGRES_DB"

# 4. Pipe the dump back in.
docker compose run --rm pg_backup sh -c "
  gunzip -c /backups/daily/luma_support-2026-05-21.sql.gz \
    | PGPASSWORD=\"$POSTGRES_PASSWORD\" psql -h postgres -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\" -v ON_ERROR_STOP=1
"

# 5. Bring the apps back.
docker compose up -d web celery celery-beat

# 6. Tail logs and verify.
docker compose logs -f web | head -40
curl -sI http://127.0.0.1:8006/system/readyz/
```

### Manual full recovery — "the box is gone"

You're rebuilding from off-site. Steps:

```sh
# On the fresh server:
cd /root && git clone https://github.com/Comm4nd0/luma-support.git
cd luma-support
cp .env.example .env && $EDITOR .env   # restore production env vars

# Pull the latest dump from the storage box.
mkdir -p /tmp/restore
rsync -azP -e "ssh -i ~/.ssh/luma_offsite -p 23" \
  "$LUMA_BACKUP_OFFSITE_USER@$LUMA_BACKUP_OFFSITE_HOST:$LUMA_BACKUP_OFFSITE_PATH/last/luma_support-latest.sql.gz" \
  /tmp/restore/

# Bring up postgres + redis only.
docker compose up -d postgres redis

# Wait for pg_isready, then pipe the dump in.
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres -c \
  "DROP DATABASE IF EXISTS $POSTGRES_DB; CREATE DATABASE $POSTGRES_DB;"
gunzip -c /tmp/restore/luma_support-latest.sql.gz \
  | docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1

# Restore media/ from the latest media archive.
rsync -azP -e "ssh -i ~/.ssh/luma_offsite -p 23" \
  "$LUMA_BACKUP_OFFSITE_USER@$LUMA_BACKUP_OFFSITE_HOST:$LUMA_BACKUP_OFFSITE_PATH/media/" \
  /tmp/restore/media/
LATEST_MEDIA="$(ls -1t /tmp/restore/media/media_*.tar.gz | head -1)"
tar -xzf "$LATEST_MEDIA" -C /root/luma-support/

# Bring the rest up.
docker compose up -d --build
```

## Trigger an ad-hoc backup

```sh
docker compose exec pg_backup /backup.sh
```

Useful before a risky migration or a manual data fix.

## Known limitations

- pg_dump locks no tables, but very long-running transactions on the
  live db can briefly block. At ~20 KB/row and a handful of clients
  it's a non-issue today; revisit at 10k+ tickets.
- Fernet-encrypted credentials *in* the dump are still encrypted — so
  the dump alone is useless without the FERNET_KEY. **The key lives in
  the production .env.** Keep a copy of that .env somewhere off-box too
  (1Password / Bitwarden / Hetzner Robot config note) or you can't
  decrypt your restored credentials.
- The off-site rsync uses `--delete` to keep the remote in sync with
  the local rotation. That means once a local dump ages out, its
  off-site copy goes too. If you need longer retention than 12 months,
  point the Storage Box at a separate path and skip `--delete`.
