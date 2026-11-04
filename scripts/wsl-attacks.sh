#!/bin/bash
# Run the attack suite as root in WSL (or on any Linux box with runsc in /usr/local/bin).
#   wsl.exe -d Ubuntu-24.04 -u root -- bash /mnt/d/.../scripts/wsl-attacks.sh <out-dir> [--only A03,A05] [--heading "..."]
# The repo is used in place. Python deps for the control-plane scenarios live in /opt/brz-venv, created on first use.
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$1"
shift
VENV=/opt/brz-venv
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q pydantic==2.13.4 httpx==0.28.1
fi
cd "$REPO" || exit 1
mkdir -p /srv/brz-attacks /var/lib/brz/bundles
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$REPO:$REPO/sandbox/runner" \
  timeout -k 10 1500 "$VENV/bin/python" -m tests.attacks --out "$OUT" "$@"
RC=$?
rm -rf /srv/brz-attacks
echo "exit $RC"
exit "$RC"
