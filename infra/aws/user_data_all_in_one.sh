#!/usr/bin/env bash
set -euxo pipefail

exec > >(tee -a /var/log/audiencias-bootstrap.log) 2>&1

REPO_URL="__REPO_URL__"
BRANCH="__BRANCH__"
APP_USER="ec2-user"
APP_HOME="/home/${APP_USER}"
PROJECT_DIR="${APP_HOME}/Trabajo-parcial-3---Big-data"

if id ubuntu >/dev/null 2>&1; then
  APP_USER="ubuntu"
  APP_HOME="/home/${APP_USER}"
  PROJECT_DIR="${APP_HOME}/Trabajo-parcial-3---Big-data"
fi

install_packages() {
  if command -v dnf >/dev/null 2>&1; then
    dnf update -y
    dnf install -y --allowerasing git make python3.11 python3.11-pip python3.11-devel docker curl-minimal unzip tar gzip gcc
  elif command -v apt-get >/dev/null 2>&1; then
    apt-get update -y
    DEBIAN_FRONTEND=noninteractive apt-get install -y git make python3 python3-venv python3-pip docker.io docker-compose-plugin curl unzip tar gzip
  else
    echo "No se encontro dnf ni apt-get" >&2
    exit 1
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

systemctl enable --now docker
usermod -aG docker "${APP_USER}" || true

if ! docker compose version >/dev/null 2>&1; then
  mkdir -p /usr/local/lib/docker/cli-plugins
  curl -fsSL "https://github.com/docker/compose/releases/download/v2.33.1/docker-compose-linux-x86_64" \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
  chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
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

if command -v python3.11 >/dev/null 2>&1; then
  sudo -u "${APP_USER}" bash -lc "cd '${PROJECT_DIR}' && make PYTHON3=python3.11 setup-a setup-b setup-c setup-d"
else
  sudo -u "${APP_USER}" bash -lc "cd '${PROJECT_DIR}' && make setup-a setup-b setup-c setup-d"
fi

sudo -u "${APP_USER}" bash -lc "cd '${PROJECT_DIR}' && make up-flink-b"

for i in $(seq 1 60); do
  if docker exec audiencias-kafka /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092 >/dev/null 2>&1; then
    break
  fi
  sleep 5
done

sudo -u "${APP_USER}" bash -lc "cd '${PROJECT_DIR}' && make topics-b"
sudo -u "${APP_USER}" bash -lc "cd '${PROJECT_DIR}' && make run-a"

cat >/etc/systemd/system/audiencias-stream.service <<EOF
[Unit]
Description=Audiencias Kafka microbatch processor
After=docker.service
Requires=docker.service

[Service]
User=${APP_USER}
WorkingDirectory=${PROJECT_DIR}/flink-jobs
Environment=KAFKA_BOOTSTRAP_INTERNAL=localhost:29092
Environment=POSTGRES_HOST=localhost
Environment=FLINK_PUBLISH_OUTPUTS=true
Environment=ALERT_HIGH_CART_PEN=1200
Environment=ALERT_CRITICAL_PAYMENT_AMOUNT_PEN=1000
Environment=ALERT_PAYMENT_FAIL_PCT=8
Environment=ALERT_HIGH_LATENCY_MS=1500
Environment=ALERT_SPIKE_MULTIPLIER=1.6
Environment=ALERT_DROP_MULTIPLIER=0.45
Environment=ALERT_SEARCH_NO_PURCHASE_MIN=20
Environment=ALERT_CART_ACTIVITY_MIN=12
Environment=AUD_COMPARADOR_MIN_VIEWS=2
Environment=AUD_INDECISO_MIN_CYCLES=1
ExecStart=${PROJECT_DIR}/.venv/bin/python -m src.main --bootstrap localhost:29092
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat >/etc/systemd/system/audiencias-backend.service <<EOF
[Unit]
Description=Audiencias dashboard realtime backend
After=docker.service audiencias-stream.service
Requires=docker.service

[Service]
User=${APP_USER}
WorkingDirectory=${PROJECT_DIR}
Environment=POSTGRES_DSN=postgresql://audiencias:audiencias@localhost:5432/audiencias
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

TOKEN="$(curl -fsS -m 2 -X PUT "http://169.254.169.254/latest/api/token" \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" 2>/dev/null || true)"

PUBLIC_HOST=""
if [ -n "${TOKEN}" ]; then
  PUBLIC_HOST="$(curl -fsS -m 2 -H "X-aws-ec2-metadata-token: ${TOKEN}" \
    http://169.254.169.254/latest/meta-data/public-hostname 2>/dev/null || true)"
  if [ -z "${PUBLIC_HOST}" ]; then
    PUBLIC_HOST="$(curl -fsS -m 2 -H "X-aws-ec2-metadata-token: ${TOKEN}" \
      http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || true)"
  fi
else
  PUBLIC_HOST="$(curl -fsS -m 2 \
    http://169.254.169.254/latest/meta-data/public-hostname 2>/dev/null || true)"
fi

if [ -z "${PUBLIC_HOST}" ]; then
  PUBLIC_HOST="$(hostname -f)"
fi

echo "Dashboard usando PUBLIC_HOST=${PUBLIC_HOST}"
export PATH="${HOME}/.bun/bin:${PATH}"
export VITE_DATA_MODE=sse
export VITE_SSE_URL="http://${PUBLIC_HOST}:8000/events/dashboard"
export VITE_API_URL="http://${PUBLIC_HOST}:8000/api/dashboard/snapshot"
export VITE_WEBSOCKET_URL="ws://${PUBLIC_HOST}:8000/ws/dashboard"
exec bun run dev -- --host 0.0.0.0 --port 3000
EOF
chmod +x /usr/local/bin/audiencias-dashboard-start.sh

cat >/etc/systemd/system/audiencias-dashboard.service <<'EOF'
[Unit]
Description=Audiencias dashboard frontend
After=audiencias-backend.service

[Service]
User=__APP_USER__
WorkingDirectory=__PROJECT_DIR__/dashboard
ExecStart=/usr/local/bin/audiencias-dashboard-start.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sed -i "s#__APP_USER__#${APP_USER}#g; s#__PROJECT_DIR__#${PROJECT_DIR}#g" /etc/systemd/system/audiencias-dashboard.service

systemctl daemon-reload
systemctl enable --now audiencias-stream.service audiencias-backend.service audiencias-dashboard.service

sleep 15
sudo -u "${APP_USER}" bash -lc "cd '${PROJECT_DIR}' && make produce-b FILE=simulator/output/base/events.jsonl RATE=100 LIMIT=5000" || true

echo "Bootstrap terminado."
echo "Logs: /var/log/audiencias-bootstrap.log"
echo "Servicios: audiencias-stream, audiencias-backend, audiencias-dashboard"
