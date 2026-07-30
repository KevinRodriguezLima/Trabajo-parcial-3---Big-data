.PHONY: help setup-a run-a test-a validate-a all-scenarios-a

PYTHON3 ?= python3
PYTHON := .venv/bin/python
PIP := .venv/bin/pip

help:
	@echo "setup-a          Crear entorno e instalar dependencias de A"
	@echo "run-a            Ejecutar una simulación BASE"
	@echo "test-a           Ejecutar pruebas de A"
	@echo "validate-a       Validar la salida BASE de A"
	@echo "all-scenarios-a  Ejecutar todos los escenarios de A"

setup-a:
	$(PYTHON3) -m venv .venv
	$(PIP) install -r simulator/requirements.txt

run-a:
	cd simulator && ../$(PYTHON) run.py --scenario BASE

test-a:
	cd simulator && ../$(PYTHON) -m unittest discover -s tests -v

validate-a:
	$(PYTHON) simulator/scripts/validate_output.py simulator/output/base/events.jsonl

all-scenarios-a:
	cd simulator && PYTHON=../$(PYTHON) ./scripts/run_all_scenarios.sh

# --- Parte B: infraestructura y producers ---------------------------------

.PHONY: help-b setup-b env-b up-b up-tools-b up-flink-b down-b down-flink-b \
	ps-b logs-b sim-b topics-b describe-b evidence-b smoke-b test-b reset-b \
	produce-b store-b psql-b count-b bench-b failover-b

COMPOSE_B := docker compose --env-file infra/.env -f infra/compose.yaml
COMPOSE_FLINK_B := $(COMPOSE_B) -f infra/compose.flink.yaml

help-b:
	@echo "setup-b          Instalar las dependencias de B en .venv"
	@echo "env-b            Crear infra/.env a partir de infra/.env.example"
	@echo "up-b             Levantar Kafka"
	@echo "up-tools-b       Levantar Kafka y la consola web"
	@echo "up-flink-b       Levantar Kafka, JobManager y TaskManager"
	@echo "down-b           Bajar el stack de Kafka"
	@echo "down-flink-b     Bajar el stack de Kafka y Flink"
	@echo "ps-b             Estado de los contenedores"
	@echo "logs-b           Seguir los logs del broker"
	@echo "sim-b            Correr el simulador de A hacia infra/data"
	@echo "topics-b         Crear los topics del contrato de forma idempotente"
	@echo "describe-b       Comparar los topics reales contra el contrato"
	@echo "evidence-b       Guardar ese reporte en artifacts/parte-b"
	@echo "smoke-b          Publicar y consumir un evento por topic"
	@echo "produce-b        Publicar un JSONL del simulador (FILE, RATE, LIMIT)"
	@echo "store-b          Consumir hacia PostgreSQL (Ctrl-C para cerrar)"
	@echo "count-b          Contar lo almacenado en el event store"
	@echo "bench-b          Medir throughput y latencia (SCENARIO, DURATION)"
	@echo "failover-b       Tumbar el broker a media corrida y medir la pérdida"
	@echo "psql-b           Abrir psql contra el event store"
	@echo "test-b           Ejecutar las pruebas de B"
	@echo "reset-b          Borrar los volúmenes del stack (destructivo)"

setup-b:
	$(PIP) install -r producers/requirements.txt

env-b:
	@test -f infra/.env || cp infra/.env.example infra/.env
	@for key in $$(grep -oE '^[A-Z_][A-Z0-9_]*=' infra/.env.example | tr -d '='); do \
		grep -q "^$$key=" infra/.env || echo "AVISO: falta $$key en infra/.env (ver infra/.env.example)"; \
	done
	@echo "infra/.env listo"

up-b: env-b
	$(COMPOSE_B) up -d

up-tools-b: env-b
	$(COMPOSE_B) --profile tools up -d

up-flink-b: env-b
	@mkdir -p infra/checkpoints infra/savepoints
	$(COMPOSE_FLINK_B) up -d

down-b: env-b
	$(COMPOSE_B) down

down-flink-b: env-b
	$(COMPOSE_FLINK_B) down

ps-b: env-b
	$(COMPOSE_B) ps

logs-b: env-b
	$(COMPOSE_B) logs -f kafka

sim-b: env-b
	$(COMPOSE_B) --profile sim up --build simulator

topics-b:
	$(PYTHON) infra/scripts/create_topics.py

describe-b:
	$(PYTHON) infra/scripts/describe_topics.py

evidence-b:
	$(PYTHON) infra/scripts/describe_topics.py --json artifacts/parte-b/topics.json

smoke-b:
	$(PYTHON) infra/scripts/smoke_test.py

FILE ?= simulator/output/base/events.jsonl
RATE ?=
LIMIT ?=
SCENARIO ?= BASE
DURATION ?= 20

produce-b:
	$(PYTHON) producers/run.py --file $(FILE) \
		$(if $(RATE),--rate $(RATE)) $(if $(LIMIT),--limit $(LIMIT))

store-b:
	$(PYTHON) producers/consumer_store.py

bench-b:
	$(PYTHON) producers/benchmark.py --scenario $(SCENARIO) --duration $(DURATION)

failover-b: env-b
	./infra/scripts/test_failover.sh

count-b: env-b
	@$(COMPOSE_B) exec -T postgres psql -U $${POSTGRES_USER:-audiencias} \
		-d $${POSTGRES_DB:-audiencias} -c \
		"SELECT kafka_topic, count(*) FROM events GROUP BY 1 ORDER BY 1;" -c \
		"SELECT run_id, publicados, enviados, rechazados, fallidos FROM runs ORDER BY started_at DESC LIMIT 5;"

psql-b: env-b
	$(COMPOSE_B) exec postgres psql -U $${POSTGRES_USER:-audiencias} -d $${POSTGRES_DB:-audiencias}

test-b:
	cd producers && ../$(PYTHON) -m unittest discover -s tests -v

reset-b: env-b
	@echo "Esto borra el volumen del broker y todos los eventos publicados."
	@printf "Escribe 'si' para continuar: "; read answer; [ "$$answer" = "si" ]
	$(COMPOSE_FLINK_B) down -v
	rm -rf infra/checkpoints infra/savepoints

# --- Parte C: Flink jobs --------------------------------------------------

.PHONY: setup-c test-c test-integration-c stream-c submit-c count-c

setup-c:
	$(PIP) install -r flink-jobs/requirements.txt

test-c:
	cd flink-jobs && ../$(PYTHON) -m unittest discover -s tests -v

test-integration-c:
	cd flink-jobs && ../$(PYTHON) -m unittest tests/test_integration.py -v

stream-c: env-b
	cd flink-jobs && KAFKA_BOOTSTRAP_INTERNAL=localhost:29092 POSTGRES_HOST=localhost \
		../$(PYTHON) -m src.main --bootstrap localhost:29092

submit-c:
	docker exec audiencias-flink-jobmanager bash -lc \
		"python -m pip install -r /opt/flink/jobs/requirements.txt && flink run -py /opt/flink/jobs/src/main.py"

count-c: env-b
	@$(COMPOSE_B) exec -T postgres psql -U $${POSTGRES_USER:-audiencias} \
		-d $${POSTGRES_DB:-audiencias} -c \
		"SELECT metric_type, count(*) FROM flink_metrics GROUP BY 1 ORDER BY 1;" -c \
		"SELECT audience_type, count(*) FROM audience_classifications GROUP BY 1 ORDER BY 1;" -c \
		"SELECT alert_type, severity, count(*) FROM alerts_anomalies GROUP BY 1, 2 ORDER BY 1;"

# --- Parte D: dashboard conectado -----------------------------------------

.PHONY: setup-d backend-d dashboard-d

setup-d:
	$(PIP) install -r dashboard/backend/requirements.txt
	cd dashboard && bun install

backend-d:
	POSTGRES_DSN=postgresql://audiencias:audiencias@localhost:5432/audiencias \
		$(PYTHON) -m uvicorn backend.realtime_backend:app --app-dir dashboard --host 0.0.0.0 --port 8000

dashboard-d:
	cd dashboard && VITE_DATA_MODE=sse VITE_SSE_URL=http://localhost:8000/events/dashboard \
		VITE_API_URL=http://localhost:8000/api/dashboard/snapshot bun run dev -- --host 0.0.0.0


