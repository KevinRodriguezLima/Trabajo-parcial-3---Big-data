#!/usr/bin/env bash
set -euxo pipefail

exec > >(tee -a /var/log/audiencias-producer-bootstrap.log) 2>&1

REPO_URL="__REPO_URL__"
BRANCH="__BRANCH__"
DATA_PRIVATE_IP="__DATA_PRIVATE_IP__"
PRODUCER_RATE="__PRODUCER_RATE__"
PRODUCER_LIMIT="__PRODUCER_LIMIT__"
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

install_packages

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

sudo -u "${APP_USER}" bash -lc "cd '${PROJECT_DIR}' && .venv/bin/pip install --upgrade pip && .venv/bin/pip install -r simulator/requirements.txt -r producers/requirements.txt"
sudo -u "${APP_USER}" bash -lc "cd '${PROJECT_DIR}' && .venv/bin/python simulator/run.py --scenario BASE"

cat >/usr/local/bin/audiencias-producer-loop.sh <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "${PROJECT_DIR}"
export POSTGRES_DSN="${POSTGRES_DSN}"
while true; do
  .venv/bin/python producers/run.py \\
    --file simulator/output/base/events.jsonl \\
    --bootstrap "${KAFKA_BOOTSTRAP}" \\
    --rate "${PRODUCER_RATE}" \\
    --limit "${PRODUCER_LIMIT}" || true
  sleep 2
done
EOF
chmod +x /usr/local/bin/audiencias-producer-loop.sh

cat >/etc/systemd/system/audiencias-producer.service <<EOF
[Unit]
Description=Audiencias continuous Kafka producer
After=network-online.target
Wants=network-online.target

[Service]
User=${APP_USER}
WorkingDirectory=${PROJECT_DIR}
ExecStart=/usr/local/bin/audiencias-producer-loop.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now audiencias-producer.service

cat >/opt/audiencias-producer.env <<EOF
DATA_PRIVATE_IP=${DATA_PRIVATE_IP}
KAFKA_BOOTSTRAP=${KAFKA_BOOTSTRAP}
POSTGRES_DSN=${POSTGRES_DSN}
PRODUCER_RATE=${PRODUCER_RATE}
PRODUCER_LIMIT=${PRODUCER_LIMIT}
EOF

echo "Nodo PRODUCER listo."
echo "Publicando continuamente hacia ${KAFKA_BOOTSTRAP} a ${PRODUCER_RATE} eventos/s."
