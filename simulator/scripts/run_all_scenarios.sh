#!/usr/bin/env bash
set -euo pipefail

AGENTS="${AGENTS:-120}"
DURATION="${DURATION:-15}"
SPEED="${SPEED:-3600}"
PYTHON="${PYTHON:-python3}"

for SCENARIO in BASE NAVIDAD CYBER_MONDAY BLACK_FRIDAY FIESTAS_PATRIAS CAMPANA_ESCOLAR DIA_DEL_PADRE; do
  echo "============================================================"
  echo "Ejecutando $SCENARIO"
  "$PYTHON" run.py \
    --scenario "$SCENARIO" \
    --agents "$AGENTS" \
    --duration "$DURATION" \
    --speed "$SPEED" \
    --no-console
done
