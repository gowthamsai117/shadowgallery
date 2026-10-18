#!/usr/bin/env bash
set -euo pipefail

# ShadowGallery target provisioning for a disposable Ubuntu Server 24.04 VM.
# Do not run on a production host or expose the intentionally vulnerable app publicly.

APP_DIR="/opt/shadowgallery"
SERVICE_USER="www-data"
FLAG="sg{shadowgallery_root_path_complete}"
UPLOAD_TOKEN="sg-worker-$(openssl rand -hex 8)"
APP_SECRET="$(openssl rand -hex 32)"
export DEBIAN_FRONTEND=noninteractive

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run with sudo: sudo bash build.sh"
  exit 1
fi

apt-get update
apt-get install -y --no-install-recommends   python3 python3-venv python3-pip nginx openssh-server sudo curl git   ca-certificates file

id -u shadowgallery >/dev/null 2>&1 || useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin shadowgallery

rm -rf "$APP_DIR"
git clone --depth 1 https://github.com/gowthamsai117/shadowgallery.git "$APP_DIR"
chown -R root:root "$APP_DIR"
chmod -R a-w "$APP_DIR"

python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0750 /var/lib/shadowgallery/uploads
install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0750 /var/lib/shadowgallery/instance

cat > /etc/shadowgallery.env <<EOF
SG_SECRET_KEY=$APP_SECRET
SG_DATABASE=/var/lib/shadowgallery/instance/shadowgallery.db
SG_UPLOAD_DIR=/var/lib/shadowgallery/uploads
SG_UPLOAD_TOKEN=$UPLOAD_TOKEN
EOF
chmod 640 /etc/shadowgallery.env
chown root:"$SERVICE_USER" /etc/shadowgallery.env

cat > /etc/systemd/system/shadowgallery.service <<EOF
[Unit]
Description=ShadowGallery CTF Web Application
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=/etc/shadowgallery.env
ExecStart=$APP_DIR/.venv/bin/gunicorn --workers 2 --bind 127.0.0.1:5000 run:app
Restart=on-failure
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
"$APP_DIR/.venv/bin/pip" install gunicorn

cat > /etc/nginx/sites-available/shadowgallery <<'EOF'
server {
    listen 80 default_server;
    server_name _;
    server_tokens off;
    location /static/ {
        alias /opt/shadowgallery/app/static/;
        expires 1h;
    }
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
EOF
rm -f /etc/nginx/sites-enabled/default
ln -sfn /etc/nginx/sites-available/shadowgallery /etc/nginx/sites-enabled/shadowgallery
nginx -t

# Intentional second-stage privilege escalation: service user can edit this config,
# and the root-owned maintenance utility evaluates POST_ROTATE_CMD from it.
install -d -o root -g root -m 0755 /opt/gallery
cat > /opt/gallery/maintenance.conf <<'EOF'
MAINTENANCE_NOTE="weekly gallery rotation"
POST_ROTATE_CMD="true"
EOF
chown "$SERVICE_USER":"$SERVICE_USER" /opt/gallery/maintenance.conf
chmod 664 /opt/gallery/maintenance.conf

cat > /usr/local/bin/gallery-maintenance <<'EOF'
#!/bin/bash
set -e
# INTENTIONAL CTF MISCONFIGURATION: privileged script sources a service-writable file.
source /opt/gallery/maintenance.conf
/usr/bin/logger "$MAINTENANCE_NOTE"
if [[ -n "${POST_ROTATE_CMD:-}" ]]; then
  /bin/bash -c "$POST_ROTATE_CMD"
fi
EOF
chown root:root /usr/local/bin/gallery-maintenance
chmod 0755 /usr/local/bin/gallery-maintenance
cat > /etc/sudoers.d/shadowgallery-maintenance <<'EOF'
www-data ALL=(root) NOPASSWD: /usr/local/bin/gallery-maintenance
EOF
chmod 0440 /etc/sudoers.d/shadowgallery-maintenance
visudo -cf /etc/sudoers.d/shadowgallery-maintenance

install -d -o root -g root -m 0700 /root
printf '%s\n' "$FLAG" > /root/proof.txt
chmod 0400 /root/proof.txt

# Keep only SSH and HTTP reachable; use a host-only/private lab network.
if command -v ufw >/dev/null 2>&1; then
  ufw allow 22/tcp || true
  ufw allow 80/tcp || true
fi

systemctl daemon-reload
systemctl enable --now ssh
systemctl enable --now shadowgallery
systemctl enable --now nginx
systemctl restart shadowgallery nginx

echo
echo "[+] ShadowGallery deployed."
echo "[+] Web: http://<TARGET-IP>/"
echo "[+] Upload token is stored in /etc/shadowgallery.env (discover it through the intended IDOR path)."
echo "[+] Root flag: /root/proof.txt"
echo "[!] Keep this VM isolated; the web app and sudo maintenance configuration are intentionally vulnerable."
