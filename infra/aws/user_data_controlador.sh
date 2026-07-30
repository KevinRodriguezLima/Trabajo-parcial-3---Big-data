#!/usr/bin/env bash
set -euxo pipefail

exec > >(tee -a /var/log/audiencias-controlador-bootstrap.log) 2>&1

REPO_URL="https://github.com/KevinRodriguezLima/Trabajo-parcial-3---Big-data.git"
BRANCH="main"
APP_USER="ec2-user"
APP_HOME="/home/${APP_USER}"
PROJECT_DIR="${APP_HOME}/Trabajo-parcial-3---Big-data"

if id ubuntu >/dev/null 2>&1; then
  APP_USER="ubuntu"
  APP_HOME="/home/${APP_USER}"
  PROJECT_DIR="${APP_HOME}/Trabajo-parcial-3---Big-data"
fi

if command -v dnf >/dev/null 2>&1; then
  dnf update -y
  dnf install -y --allowerasing git python3.11 python3.11-pip python3.11-devel gcc make unzip curl-minimal
elif command -v apt-get >/dev/null 2>&1; then
  apt-get update -y
  DEBIAN_FRONTEND=noninteractive apt-get install -y git python3 python3-pip python3-venv python3-dev gcc make unzip curl
else
  echo "No se encontro dnf ni apt-get" >&2
  exit 1
fi

if command -v python3.11 >/dev/null 2>&1; then
  python3.11 -m pip install --upgrade pip
  python3.11 -m pip install boto3 botocore
else
  python3 -m pip install --upgrade pip
  python3 -m pip install boto3 botocore
fi

if [ ! -d "${PROJECT_DIR}/.git" ]; then
  sudo -u "${APP_USER}" git clone --branch "${BRANCH}" "${REPO_URL}" "${PROJECT_DIR}"
else
  sudo -u "${APP_USER}" bash -lc "cd '${PROJECT_DIR}' && git fetch origin && git checkout '${BRANCH}' && git pull --ff-only"
fi

cat > "${APP_HOME}/crear_proyecto03.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "${PROJECT_DIR}"
git pull --ff-only
python3 infra/aws/levantar_audiencias_ec2.py --start \\
  --region us-east-1 \\
  --ami-id ami-03f4fd1e8233bd64d \\
  --key-name cluster \\
  --subnet-id subnet-0346fd19f61aafdcd \\
  --security-group-id sg-00c82fc157b6a0478 \\
  --instance-type t3.large \\
  --instance-profile LabInstanceProfile
EOF

cat > "${APP_HOME}/crear_proyecto03_distribuido.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "${PROJECT_DIR}"
git pull --ff-only
python3 infra/aws/levantar_audiencias_distribuido.py --start \\
  --region us-east-1 \\
  --ami-id ami-03f4fd1e8233bd64d \\
  --key-name cluster \\
  --subnet-id subnet-0346fd19f61aafdcd \\
  --security-group-id sg-00c82fc157b6a0478 \\
  --data-instance-type t3.large \\
  --app-instance-type t3.large \\
  --producer-instance-type t3.small \\
  --producer-rate 100 \\
  --producer-limit 5000 \\
  --instance-profile LabInstanceProfile
EOF

chmod +x "${APP_HOME}/crear_proyecto03.sh" "${APP_HOME}/crear_proyecto03_distribuido.sh"
chown -R "${APP_USER}:${APP_USER}" "${PROJECT_DIR}" "${APP_HOME}/crear_proyecto03.sh" "${APP_HOME}/crear_proyecto03_distribuido.sh"

cat > "${APP_HOME}/README_PROYECTO03.txt" <<EOF
Controlador listo.

1. Revisa el log de instalacion:
   sudo tail -f /var/log/audiencias-controlador-bootstrap.log

2. Crea la instancia todo-en-uno:
   ./crear_proyecto03.sh

   O crea el despliegue distribuido de 3 instancias:
   ./crear_proyecto03_distribuido.sh

3. Lista instancias creadas:
   cd ${PROJECT_DIR}
   python3 infra/aws/levantar_audiencias_ec2.py --check

4. Borra la instancia del proyecto:
   cd ${PROJECT_DIR}
   python3 infra/aws/levantar_audiencias_ec2.py --delete
EOF

chown "${APP_USER}:${APP_USER}" "${APP_HOME}/README_PROYECTO03.txt"

echo "Controlador Proyecto 03 listo."
echo "Ejecuta: /home/${APP_USER}/crear_proyecto03.sh"
echo "Distribuido: /home/${APP_USER}/crear_proyecto03_distribuido.sh"
