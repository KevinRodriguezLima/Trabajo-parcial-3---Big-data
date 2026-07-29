#!/usr/bin/env bash
# Publica sin parar, tumba el broker a mitad de la corrida y compara
# publicados, confirmados y filas realmente almacenadas.
#
# El consumidor usa un grupo nuevo que arranca al final de los topics: así se
# miden solo los eventos de esta corrida y no el histórico que haya quedado de
# benchmarks anteriores.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"

FILE="${FILE:-simulator/output/base/events.jsonl}"
RATE="${RATE:-200}"
LIMIT="${LIMIT:-9000}"
OUTAGE_AT="${OUTAGE_AT:-15}"
RECOVERY_AT="${RECOVERY_AT:-30}"
PG_USER="${POSTGRES_USER:-audiencias}"
PG_DB="${POSTGRES_DB:-audiencias}"
GROUP_ID="failover-$$"

WORKDIR="$(mktemp -d)"
# stdout y stderr van a archivos distintos: los logs traen dicts de Python que
# empiezan por '{' y confundirían al lector del resumen JSON.
RUN_OUT="$WORKDIR/run.json"
RUN_LOG="$WORKDIR/run.log"
STORE_OUT="$WORKDIR/store.json"
STORE_LOG="$WORKDIR/store.log"
RUN_PID=""
STORE_PID=""

# Función y no variable: la ruta del repo puede tener espacios.
compose() {
    docker compose --env-file "$ROOT/infra/.env" -f "$ROOT/infra/compose.yaml" "$@"
}

cleanup() {
    [ -n "$STORE_PID" ] && kill -INT "$STORE_PID" 2>/dev/null || true
    [ -n "$RUN_PID" ] && kill -INT "$RUN_PID" 2>/dev/null || true
    # El broker queda levantado aunque la prueba falle a mitad de camino.
    compose start kafka >/dev/null 2>&1 || true
}
trap cleanup EXIT

count_events() {
    docker exec "$(compose ps -q postgres)" \
        psql -U "$PG_USER" -d "$PG_DB" -tAc "SELECT count(*) FROM events;" 2>/dev/null |
        tr -d '[:space:]'
}

wait_healthy() {
    for _ in $(seq 1 30); do
        if [ "$(docker inspect --format '{{.State.Health.Status}}' audiencias-kafka 2>/dev/null)" = "healthy" ]; then
            return 0
        fi
        sleep 2
    done
    echo "El broker no volvió a estado healthy" >&2
    return 1
}

cd "$ROOT"

echo "== Prueba de tolerancia a fallos =="
echo "archivo=$FILE rate=$RATE limit=$LIMIT corte=${OUTAGE_AT}s recuperación=${RECOVERY_AT}s"
echo "grupo del consumidor: $GROUP_ID (desde el final de los topics)"
echo

wait_healthy
BASELINE="$(count_events)"
echo "Filas en el event store antes de empezar: $BASELINE"

"$PYTHON" producers/consumer_store.py --group-id "$GROUP_ID" --from-latest \
    >"$STORE_OUT" 2>"$STORE_LOG" &
STORE_PID=$!

# Publicar antes de que el consumidor tenga particiones asignadas dejaría
# fuera de la medición todo lo enviado en ese hueco.
for _ in $(seq 1 30); do
    grep -q "particiones asignadas" "$STORE_LOG" && break
    sleep 1
done
if ! grep -q "particiones asignadas" "$STORE_LOG"; then
    echo "El consumidor no recibió particiones; se aborta" >&2
    exit 1
fi
echo "[$(date +%T)] consumidor listo"

"$PYTHON" producers/run.py --file "$FILE" --rate "$RATE" --limit "$LIMIT" \
    >"$RUN_OUT" 2>"$RUN_LOG" &
RUN_PID=$!

sleep "$OUTAGE_AT"
echo "[$(date +%T)] deteniendo el broker"
compose stop kafka >/dev/null

sleep "$((RECOVERY_AT - OUTAGE_AT))"
echo "[$(date +%T)] levantando el broker"
compose start kafka >/dev/null
wait_healthy
echo "[$(date +%T)] broker recuperado"

set +e
wait "$RUN_PID"
RUN_STATUS=$?
set -e
RUN_PID=""
echo "[$(date +%T)] publicación terminada (código $RUN_STATUS)"

# Margen para que el consumidor drene lo que quedó pendiente.
PREVIO=-1
for _ in $(seq 1 30); do
    ACTUAL="$(count_events)"
    [ "$ACTUAL" = "$PREVIO" ] && break
    PREVIO="$ACTUAL"
    sleep 2
done

kill -INT "$STORE_PID" 2>/dev/null || true
wait "$STORE_PID" 2>/dev/null || true
STORE_PID=""

FINAL="$(count_events)"
echo

set +e
"$PYTHON" - "$RUN_OUT" "$BASELINE" "$FINAL" <<'PY'
import json
import sys

ruta, baseline, final = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
texto = open(ruta, encoding="utf-8").read().strip()
if not texto:
    print("La publicación no dejó resumen: revisá el log", file=sys.stderr)
    sys.exit(2)
resumen = json.loads(texto)

publicados = resumen.get("publicados", 0)
enviados = resumen.get("enviados", 0)
rechazados = resumen.get("rechazados", 0)
fallidos = resumen.get("fallidos", 0)
almacenados = final - baseline

print(f"{'MÉTRICA':<34}{'VALOR':>10}")
print("-" * 44)
print(f"{'Publicados (encolados)':<34}{publicados:>10}")
print(f"{'Confirmados por el broker':<34}{enviados:>10}")
print(f"{'Rechazados al dead-letter':<34}{rechazados:>10}")
print(f"{'Entregas fallidas':<34}{fallidos:>10}")
print(f"{'Filas nuevas en el event store':<34}{almacenados:>10}")
print()

problemas = []
if publicados - enviados:
    problemas.append(f"{publicados - enviados} mensajes encolados nunca fueron confirmados")
if fallidos:
    problemas.append(f"{fallidos} entregas devolvieron error")
if enviados - almacenados > 0:
    problemas.append(f"{enviados - almacenados} mensajes confirmados no llegaron al event store")
elif almacenados > enviados:
    print(f"Nota: el event store recibió {almacenados - enviados} filas de otras corridas.")

if problemas:
    print("PÉRDIDA DETECTADA:")
    for problema in problemas:
        print(f"  - {problema}")
    sys.exit(1)

print("Sin pérdida: todo lo encolado se confirmó y se almacenó.")
PY
RESULTADO=$?
set -e

echo
echo "Log del consumidor:  $STORE_LOG"
echo "Log de publicación:  $RUN_LOG"
exit $RESULTADO
