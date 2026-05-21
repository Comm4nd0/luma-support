#!/usr/bin/env bash
# scripts/backup_media.sh — snapshot the user-uploaded media directory.
#
# pg_dump only covers the database. Files in ./media/ (CV uploads, KB
# article images, ticket attachments, client documents) live on disk and
# would be lost if the disk dies — pg_dump won't save you.
#
# This script tarballs ./media/ and writes a dated archive into the
# pg_backups Docker volume (so it sits next to the db dumps and goes
# off-site with them via backup_offsite.sh).
#
# Run from the repo root:
#   ./scripts/backup_media.sh
#
# Cron suggestion (host crontab):
#   0 3 * * *  cd /root/luma-support && ./scripts/backup_media.sh >> /var/log/luma-media-backup.log 2>&1

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

STAMP="$(date -u +%Y-%m-%d_%H%M%S)"
ARCHIVE="media_${STAMP}.tar.gz"
TARGET_VOLUME="pg_backups"  # same volume as db dumps, see docker-compose.yml

# How many media archives to keep on-box (matches pg_backup's daily window).
KEEP_DAYS="${LUMA_MEDIA_KEEP_DAYS:-7}"

if [ ! -d "media" ]; then
  echo "no media/ directory — nothing to back up. exiting."
  exit 0
fi

echo "==> creating $ARCHIVE"
TMP_TAR="$(mktemp -t luma-media-XXXXXX.tar.gz)"
trap 'rm -f "$TMP_TAR"' EXIT
tar --create --gzip --file "$TMP_TAR" --directory "$REPO_ROOT" media/
SIZE="$(du -h "$TMP_TAR" | awk '{print $1}')"
echo "    archive size: $SIZE"

# Find the actual host path for the pg_backups volume. Using `docker
# volume inspect` keeps us working even if the project name changes.
PROJECT="$(basename "$REPO_ROOT")"
VOLUME_NAME="${PROJECT}_${TARGET_VOLUME}"
HOST_PATH="$(docker volume inspect --format '{{ .Mountpoint }}' "$VOLUME_NAME" 2>/dev/null || true)"

if [ -z "$HOST_PATH" ]; then
  echo "ERROR: can't find docker volume '$VOLUME_NAME'."
  echo "       run 'docker compose up -d pg_backup' first."
  exit 1
fi

# Store media archives in a sub-dir so the rotation logic below doesn't
# trip over the postgres-backup-local image's own files.
MEDIA_DIR="$HOST_PATH/media"
mkdir -p "$MEDIA_DIR"

mv "$TMP_TAR" "$MEDIA_DIR/$ARCHIVE"
chmod 0600 "$MEDIA_DIR/$ARCHIVE"
echo "    wrote $MEDIA_DIR/$ARCHIVE"

# Rotation: drop archives older than KEEP_DAYS days.
echo "==> rotating (keep last $KEEP_DAYS days)"
find "$MEDIA_DIR" -maxdepth 1 -name 'media_*.tar.gz' -mtime "+$KEEP_DAYS" -print -delete || true

echo "==> done"
