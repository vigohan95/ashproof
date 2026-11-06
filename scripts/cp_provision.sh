#!/bin/bash
# Runs ON the control-plane VM as root: packages, venv, service, HTTPS. Safe to run again.
# Usage: cp_provision.sh <public hostname>
set -euo pipefail
HOST="$1"
APP=/opt/ashproof/app
export DEBIAN_FRONTEND=noninteractive

if [ ! -f /swapfile ]; then
  fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

apt-get update -qq
apt-get install -y -qq python3-venv caddy >/dev/null

id ashproof >/dev/null 2>&1 || useradd --system --home /var/lib/ashproof --shell /usr/sbin/nologin ashproof
mkdir -p /var/lib/ashproof /etc/ashproof
chown ashproof:ashproof /var/lib/ashproof
chown root:ashproof /etc/ashproof/env
chmod 0640 /etc/ashproof/env

[ -d /opt/ashproof/venv ] || python3 -m venv /opt/ashproof/venv
/opt/ashproof/venv/bin/pip install -q --upgrade pip
/opt/ashproof/venv/bin/pip install -q --force-reinstall --no-deps "$APP"
/opt/ashproof/venv/bin/pip install -q "$APP"

cat > /etc/systemd/system/ashproof.service <<'EOF'
[Unit]
Description=Ashproof control plane
After=network-online.target
Wants=network-online.target

[Service]
User=ashproof
Group=ashproof
EnvironmentFile=/etc/ashproof/env
WorkingDirectory=/var/lib/ashproof
ExecStart=/opt/ashproof/venv/bin/uvicorn apps.control_plane.app:app --host 127.0.0.1 --port 8000 --no-server-header
Restart=always
RestartSec=3
MemoryMax=640M
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
PrivateDevices=yes
ReadWritePaths=/var/lib/ashproof

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/caddy/Caddyfile <<EOF
$HOST {
	request_body {
		max_size 2MB
	}
	header {
		X-Content-Type-Options nosniff
		X-Frame-Options DENY
		Referrer-Policy no-referrer
		-Server
	}
	encode gzip
	reverse_proxy 127.0.0.1:8000
}
EOF

ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null

systemctl daemon-reload
systemctl enable --now ashproof >/dev/null
systemctl restart ashproof
systemctl enable caddy >/dev/null
systemctl restart caddy
sleep 4
systemctl is-active ashproof caddy
curl -fsS http://127.0.0.1:8000/health
echo
