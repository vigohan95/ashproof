#!/bin/bash
# Redeploy HEAD to the live control plane, keeping its firewall group. Refuses while a task is running.
#   scripts/redeploy.sh [KEY=VALUE ...]
set -euo pipefail
cd "$(dirname "$0")/.."
BASE=https://45-76-6-117.sslip.io
SSH_DIR=$(grep -E '^BRZ_SSH_DIR=' .env | cut -d= -f2 | tr -d '\r')
running=$(curl -s -m 20 "$BASE/health" | python -c 'import json,sys; print(json.load(sys.stdin)["running"])')
[ "$running" = "0" ] || { echo "a task is running, not deploying"; exit 1; }
fw=$(ssh -F "$SSH_DIR/ssh_config" ashproof-cp 'grep ^VULTR_FIREWALL_GROUP_ID= /etc/ashproof/env | cut -d= -f2')
python scripts/deploy_cp.py ashproof-cp 45.76.6.117 "$fw" "$@"
curl -s -m 20 "$BASE/health"
echo
