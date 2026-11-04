#!/bin/bash
# Run one evidence module as root in WSL (needs the venv from wsl-attacks.sh):
#   wsl.exe -d Ubuntu-24.04 -u root -- bash /mnt/d/.../scripts/wsl-evidence.sh receipt_evidence --out <dir>
#   wsl.exe -d Ubuntu-24.04 -u root -- bash /mnt/d/.../scripts/wsl-evidence.sh kill_timing --out <dir> --runs 30
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
MODULE="$1"
shift
cd "$REPO" || exit 1
mkdir -p /srv/brz-attacks /var/lib/brz/bundles
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$REPO:$REPO/sandbox/runner" \
  timeout -k 10 500 /opt/brz-venv/bin/python -m "tests.attacks.$MODULE" "$@"
RC=$?
rm -rf /srv/brz-attacks
echo "exit $RC"
exit "$RC"
