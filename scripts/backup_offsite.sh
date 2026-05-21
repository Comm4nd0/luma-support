#!/usr/bin/env bash
# scripts/backup_offsite.sh — rsync local backups to a remote target.
#
# On-box backups protect against accidental deletes and bad migrations.
# Off-box backups protect against the box itself dying (disk failure,
# Hetzner outage, ransomware, somebody fat-fingering a `rm -rf`).
#
# This script rsyncs the contents of the pg_backups volume to a remote
# target — typically a Hetzner Storage Box, but any rsync-over-ssh
# endpoint works.
#
# Configure via env vars (all required):
#   LUMA_BACKUP_OFFSITE_HOST   e.g. uXXXXXX.your-storagebox.de
#   LUMA_BACKUP_OFFSITE_USER   e.g. uXXXXXX-sub1
#   LUMA_BACKUP_OFFSITE_PATH   e.g. /home/backups/luma-support
#   LUMA_BACKUP_OFFSITE_PORT   default 23 (Hetzner Storage Box uses 23)
#   LUMA_BACKUP_OFFSITE_SSH_KEY default ~/.ssh/luma_offsite (rsa or ed25519)
#
# Exit code 0 ⇒ rsync OK (or no-op if not configured).
# Exit code 1 ⇒ rsync failed.
#
# Cron suggestion (host crontab):
#   30 3 * * *  cd /root/luma-support && ./scripts/backup_offsite.sh >> /var/log/luma-offsite.log 2>&1

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

HOST="${LUMA_BACKUP_OFFSITE_HOST:-}"
USER="${LUMA_BACKUP_OFFSITE_USER:-}"
REMOTE_PATH="${LUMA_BACKUP_OFFSITE_PATH:-}"
PORT="${LUMA_BACKUP_OFFSITE_PORT:-23}"
SSH_KEY="${LUMA_BACKUP_OFFSITE_SSH_KEY:-$HOME/.ssh/luma_offsite}"

if [ -z "$HOST" ] || [ -z "$USER" ] || [ -z "$REMOTE_PATH" ]; then
  echo "off-site backups not configured (set LUMA_BACKUP_OFFSITE_HOST / USER / PATH). exiting."
  exit 0
fi

PROJECT="$(basename "$REPO_ROOT")"
VOLUME_NAME="${PROJECT}_pg_backups"
LOCAL_PATH="$(docker volume inspect --format '{{ .Mountpoint }}' "$VOLUME_NAME" 2>/dev/null || true)"

if [ -z "$LOCAL_PATH" ]; then
  echo "ERROR: can't find docker volume '$VOLUME_NAME'."
  exit 1
fi

if [ ! -f "$SSH_KEY" ]; then
  echo "ERROR: SSH key not found at $SSH_KEY"
  echo "       generate one with: ssh-keygen -t ed25519 -f $SSH_KEY -N ''"
  echo "       and add the .pub to your storage box authorized_keys."
  exit 1
fi

echo "==> rsync $LOCAL_PATH/ -> $USER@$HOST:$REMOTE_PATH/"
rsync -az --delete \
  -e "ssh -i $SSH_KEY -p $PORT -o StrictHostKeyChecking=accept-new" \
  "$LOCAL_PATH/" \
  "$USER@$HOST:$REMOTE_PATH/"

echo "==> done"
