#!/usr/bin/env bash
set -euxo pipefail

exec > >(tee -a /var/log/audiencias-data-bootstrap.log) 2>&1

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
    DEBIAN_FRONTEND=noninteractive apt-get install -y git make python3 python3-venv python3-pip docker.io docker-compose-plugin curl unzip tar gzip gcc
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

systemctl enable --now docker
usermod -aG docker "${APP_USER}" || true

if ! docker compose version >/dev/null 2>&1; then
  mkdir -p /usr/local/lib/docker/cli-plugins
  curl -fsSL "https://github.com/docker/compose/releases/download/v2.33.1/docker-compose-linux-x86_64" \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
  chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
fi

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

sudo -u "${APP_USER}" bash -lc "cd '${PROJECT_DIR}' && .venv/bin/pip install --upgrade pip && .venv/bin/pip install -r producers/requirements.txt"
sudo -u "${APP_USER}" bash -lc "cd '${PROJECT_DIR}' && make env-b"

PRIVATE_IP="$(metadata local-ipv4)"
sed -i "s#^KAFKA_ADVERTISED_EXTERNAL_HOST=.*#KAFKA_ADVERTISED_EXTERNAL_HOST=${PRIVATE_IP}#g" infra/.env
sed -i "s#^KAFKA_BOOTSTRAP_EXTERNAL=.*#KAFKA_BOOTSTRAP_EXTERNAL=${PRIVATE_IP}:29092#g" infra/.env

docker compose --env-file infra/.env -f infra/compose.yaml --profile tools up -d

for i in $(seq 1 90); do
  if docker exec audiencias-kafka /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092 >/dev/null 2>&1; then
    break
  fi
  sleep 5
done

sudo -u "${APP_USER}" bash -lc "cd '${PROJECT_DIR}' && .venv/bin/python infra/scripts/create_topics.py --bootstrap-servers '${PRIVATE_IP}:29092'"

cat >/opt/audiencias-data.env <<EOF
DATA_PRIVATE_IP=${PRIVATE_IP}
KAFKA_BOOTSTRAP=${PRIVATE_IP}:29092
POSTGRES_DSN=postgresql://audiencias:audiencias@${PRIVATE_IP}:5432/audiencias
EOF

echo "Nodo DATA listo."
echo "Kafka: ${PRIVATE_IP}:29092"
echo "PostgreSQL: ${PRIVATE_IP}:5432"
PUBLIC_HOST="$(metadata public-hostname 2>/dev/null || hostname -f)"
echo "Kafka UI: http://${PUBLIC_HOST}:8080"
