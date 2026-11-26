#!/usr/bin/env bash
set -euo pipefail
usage() {
  echo "usage: $0 --list | --backup NAME --confirm" >&2
  exit 2
}
[[ $# -gt 0 ]] || usage
if [[ "$1" == "--list" ]]; then
  velero backup get
  exit 0
fi
BACKUP=""
CONFIRM=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --backup) BACKUP="${2:-}"; shift 2 ;;
    --confirm) CONFIRM=true; shift ;;
    *) usage ;;
  esac
done
[[ -n "$BACKUP" && "$CONFIRM" == true ]] || usage
echo "==> Restoring Velero backup $BACKUP"
echo "WARNING: validate the Alembic revision before restoring any database state."
RESTORE="taskflow-restore-$(date -u +%Y%m%d-%H%M%S)"
velero restore create "$RESTORE" --from-backup "$BACKUP" --wait
velero restore describe "$RESTORE"
velero restore logs "$RESTORE"
echo "Velero objects restored. Follow runbooks/dr-restore.md for RDS and DNS validation."
