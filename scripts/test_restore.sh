#!/usr/bin/env bash
# scripts/test_restore.sh — verify a backup is actually restorable.
#
# Backups you've never tested aren't backups, they're hope. This script
# spins up a throwaway Postgres container, pipes the latest pg_dump from
# the pg_backups volume into it, and runs a couple of sanity queries.
# Nothing touches the live db.
#
# Exit code 0 ⇒ the most recent backup restored cleanly.
# Exit code 1 ⇒ no backup found.
# Exit code 2 ⇒ restore or sanity-check failed (look at the output).
#
# Run from the repo root:
#   ./scripts/test_restore.sh
#
# Cron suggestion: weekly, so you find out about a broken backup chain
# within days, not the day you actually need it.
#   0 4 * * 0  cd /root/luma-support && ./scripts/test_restore.sh >> /var/log/luma-restore-drill.log 2>&1

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PROJECT="$(basename "$REPO_ROOT")"
VOLUME_NAME="${PROJECT}_pg_backups"
PG_IMAGE="postgres:16-alpine"
TEST_CONTAINER="luma-restore-drill-$$"
TEST_PASSWORD="restore_drill_throwaway"
TEST_DB="restore_drill"

echo "==> looking for most recent dump in $VOLUME_NAME"

# postgres-backup-local writes the most recent dump to
# /backups/last/<db>-latest.sql.gz. If that's missing, fall back to the
# newest file under /backups/daily/.
LATEST_INSIDE=$(docker run --rm -v "$VOLUME_NAME:/b:ro" "$PG_IMAGE" sh -c '
  if ls /b/last/*-latest.sql.gz >/dev/null 2>&1; then
    ls -1 /b/last/*-latest.sql.gz | head -n1
  else
    find /b/daily -name "*.sql.gz" -printf "%T@ %p\n" 2>/dev/null \
      | sort -nr | awk "{print \$2}" | head -n1
  fi
')

if [ -z "$LATEST_INSIDE" ]; then
  echo "ERROR: no backup found in $VOLUME_NAME."
  echo "       hint: docker compose up -d pg_backup, wait a day, or trigger one manually:"
  echo "         docker compose exec pg_backup /backup.sh"
  exit 1
fi

echo "    will restore: $LATEST_INSIDE"

cleanup() {
  docker rm -f "$TEST_CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "==> starting throwaway postgres ($TEST_CONTAINER)"
docker run -d --rm --name "$TEST_CONTAINER" \
  -e POSTGRES_PASSWORD="$TEST_PASSWORD" \
  -e POSTGRES_DB="$TEST_DB" \
  -v "$VOLUME_NAME:/b:ro" \
  "$PG_IMAGE" >/dev/null

# Wait for it to become ready.
for i in $(seq 1 30); do
  if docker exec "$TEST_CONTAINER" pg_isready -U postgres >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
if ! docker exec "$TEST_CONTAINER" pg_isready -U postgres >/dev/null 2>&1; then
  echo "ERROR: throwaway postgres didn't come up."
  exit 2
fi

echo "==> preparing throwaway db (drop+recreate public schema)"
# pg_dump from postgres-backup-local includes CREATE SCHEMA public, but a
# fresh Postgres image already has one -- drop it first to avoid the
# inevitable "schema already exists" error.
docker exec "$TEST_CONTAINER" psql -U postgres -d "$TEST_DB" -v ON_ERROR_STOP=1 -c \
  "DROP SCHEMA IF EXISTS public CASCADE;" > /dev/null

echo "==> piping dump into throwaway db"
if ! docker exec "$TEST_CONTAINER" sh -c "
    set -e
    gunzip -c '$LATEST_INSIDE' | psql -U postgres -d '$TEST_DB' -v ON_ERROR_STOP=1 > /tmp/restore.log 2>&1
  " ; then
  echo "ERROR: restore failed. tail of log:"
  docker exec "$TEST_CONTAINER" tail -40 /tmp/restore.log || true
  exit 2
fi

echo "==> sanity checks"
QUERIES=(
  "SELECT count(*) FROM accounts_user"
  "SELECT count(*) FROM clients_client"
  "SELECT count(*) FROM tickets_ticket"
  "SELECT count(*) FROM billing_invoice"
)

FAIL=0
for q in "${QUERIES[@]}"; do
  if out=$(docker exec "$TEST_CONTAINER" psql -U postgres -d "$TEST_DB" -tAc "$q" 2>&1); then
    printf "    %-45s => %s\n" "$q" "$out"
  else
    printf "    %-45s => FAILED (%s)\n" "$q" "$out"
    FAIL=1
  fi
done

if [ "$FAIL" -ne 0 ]; then
  echo "ERROR: one or more sanity queries failed against the restored dump."
  exit 2
fi

echo "==> OK — backup is restorable."
