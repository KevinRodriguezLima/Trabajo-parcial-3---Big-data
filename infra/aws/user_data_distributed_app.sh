#!/usr/bin/env bash
set -euxo pipefail

exec > >(tee -a /var/log/audiencias-app-bootstrap.log) 2>&1

REPO_URL="__REPO_URL__"
BRANCH="__BRANCH__"
DATA_PRIVATE_IP="__DATA_PRIVATE_IP__"
APP_USER="ec2-user"
APP_HOME="/home/${APP_USER}"
PROJECT_DIR="${APP_HOME}/Trabajo-parcial-3---Big-data"
POSTGRES_DSN="postgresql://audiencias:audiencias@${DATA_PRIVATE_IP}:5432/audiencias"
KAFKA_BOOTSTRAP="${DATA_PRIVATE_IP}:29092"

if id ubuntu >/dev/null 2>&1; then
  APP_USER="ubuntu"
  APP_HOME="/home/${APP_USER}"
  PROJECT_DIR="${APP_HOME}/Trabajo-parcial-3---Big-data"
fi

install_packages() {
  if command -v dnf >/dev/null 2>&1; then
    dnf update -y
    dnf install -y --allowerasing git make python3.11 python3.11-pip python3.11-devel curl-minimal unzip tar gzip gcc
  elif command -v apt-get >/dev/null 2>&1; then
    apt-get update -y
    DEBIAN_FRONTEND=noninteractive apt-get install -y git make python3 python3-venv python3-pip curl unzip tar gzip gcc
  else
    echo "No se encontro dnf ni apt-get" >&2
    exit 1
  fi
}

metadata() {
  local path="$1"
  local token
  token="$(curl -fsS -m 2 -X PUT "http://169.254.169.254/latest/api/token" \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" 2>/dev/null || true)"
  if [ -n "${token}" ]; then
    curl -fsS -m 2 -H "X-aws-ec2-metadata-token: ${token}" "http://169.254.169.254/latest/meta-data/${path}"
  else
    curl -fsS -m 2 "http://169.254.169.254/latest/meta-data/${path}"
  fi
}

install_packages

if [ ! -f /swapfile ]; then
  fallocate -l 4G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=4096
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo "/swapfile none swap sw 0 0" >> /etc/fstab
fi

if ! command -v node >/dev/null 2>&1; then
  curl -fsSL https://rpm.nodesource.com/setup_22.x | bash - || true
  if command -v dnf >/dev/null 2>&1; then
    dnf install -y nodejs || true
  fi
fi
sudo -u "${APP_USER}" bash -lc 'if ! command -v bun >/dev/null 2>&1; then curl -fsSL https://bun.sh/install | bash; fi'

if [ ! -d "${PROJECT_DIR}/.git" ]; then
  sudo -u "${APP_USER}" git clone --branch "${BRANCH}" "${REPO_URL}" "${PROJECT_DIR}"
else
  sudo -u "${APP_USER}" bash -lc "cd '${PROJECT_DIR}' && git fetch origin && git checkout '${BRANCH}' && git pull --ff-only"
fi

cd "${PROJECT_DIR}"
if command -v python3.11 >/dev/null 2>&1; then
  python3.11 -m venv .venv
else
  python3 -m venv .venv
fi
chown -R "${APP_USER}:${APP_USER}" .venv

sudo -u "${APP_USER}" bash -lc "cd '${PROJECT_DIR}' && .venv/bin/pip install --upgrade pip && .venv/bin/pip install -r producers/requirements.txt -r flink-jobs/requirements.txt -r dashboard/backend/requirements.txt"
sudo -u "${APP_USER}" bash -lc "cd '${PROJECT_DIR}/dashboard' && export PATH=\"\$HOME/.bun/bin:\$PATH\" && bun install"

cat >/etc/systemd/system/audiencias-event-store.service <<EOF
[Unit]
Description=Audiencias event store consumer
After=network-online.target
Wants=network-online.target

[Service]
User=${APP_USER}
WorkingDirectory=${PROJECT_DIR}
Environment=POSTGRES_DSN=${POSTGRES_DSN}
ExecStart=${PROJECT_DIR}/.venv/bin/python producers/consumer_store.py --bootstrap ${KAFKA_BOOTSTRAP} --dsn ${POSTGRES_DSN}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat >/etc/systemd/system/audiencias-stream.service <<EOF
[Unit]
Description=Audiencias Kafka microbatch processor
After=network-online.target audiencias-event-store.service
Wants=network-online.target

[Service]
User=${APP_USER}
WorkingDirectory=${PROJECT_DIR}/flink-jobs
Environment=KAFKA_BOOTSTRAP_INTERNAL=${KAFKA_BOOTSTRAP}
Environment=POSTGRES_HOST=${DATA_PRIVATE_IP}
Environment=POSTGRES_DSN=${POSTGRES_DSN}
Environment=FLINK_PUBLISH_OUTPUTS=true
Environment=ALERT_HIGH_CART_PEN=1200
ExecStart=${PROJECT_DIR}/.venv/bin/python -m src.main --bootstrap ${KAFKA_BOOTSTRAP}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat >/etc/systemd/system/audiencias-backend.service <<EOF
[Unit]
Description=Audiencias dashboard realtime backend
After=network-online.target audiencias-stream.service
Wants=network-online.target

[Service]
User=${APP_USER}
WorkingDirectory=${PROJECT_DIR}
Environment=POSTGRES_DSN=${POSTGRES_DSN}
Environment=DASHBOARD_POLL_SECONDS=0.75
ExecStart=${PROJECT_DIR}/.venv/bin/python -m uvicorn backend.realtime_backend:app --app-dir dashboard --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat >/usr/local/bin/audiencias-dashboard-start.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

metadata() {
  local path="$1"
  local token
  token="$(curl -fsS -m 2 -X PUT "http://169.254.169.254/latest/api/token" \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" 2>/dev/null || true)"
  if [ -n "${token}" ]; then
    curl -fsS -m 2 -H "X-aws-ec2-metadata-token: ${token}" "http://169.254.169.254/latest/meta-data/${path}"
  else
    curl -fsS -m 2 "http://169.254.169.254/latest/meta-data/${path}"
  fi
}

PUBLIC_HOST="$(metadata public-hostname 2>/dev/null || metadata public-ipv4 2>/dev/null || hostname -f)"
echo "Dashboard usando PUBLIC_HOST=${PUBLIC_HOST}"
export PATH="${HOME}/.bun/bin:${PATH}"
export VITE_DATA_MODE=sse
export VITE_SSE_URL="http://${PUBLIC_HOST}:8000/events/dashboard"
export VITE_API_URL="http://${PUBLIC_HOST}:8000/api/dashboard/snapshot"
export VITE_WEBSOCKET_URL="ws://${PUBLIC_HOST}:8000/ws/dashboard"
exec bun run dev -- --host 0.0.0.0 --port 3000
EOF
chmod +x /usr/local/bin/audiencias-dashboard-start.sh

cat >/etc/systemd/system/audiencias-dashboard.service <<EOF
[Unit]
Description=Audiencias dashboard frontend
After=audiencias-backend.service

[Service]
User=${APP_USER}
WorkingDirectory=${PROJECT_DIR}/dashboard
ExecStart=/usr/local/bin/audiencias-dashboard-start.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now audiencias-event-store.service audiencias-stream.service audiencias-backend.service audiencias-dashboard.service

cat >/opt/audiencias-app.env <<EOF
DATA_PRIVATE_IP=${DATA_PRIVATE_IP}
KAFKA_BOOTSTRAP=${KAFKA_BOOTSTRAP}
POSTGRES_DSN=${POSTGRES_DSN}
EOF

PUBLIC_HOST="$(metadata public-hostname 2>/dev/null || hostname -f)"
echo "Nodo APP listo."
echo "Dashboard: http://${PUBLIC_HOST}:3000"
echo "Backend: http://${PUBLIC_HOST}:8000/health"
