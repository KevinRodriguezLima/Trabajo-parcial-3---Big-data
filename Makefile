.PHONY: help setup-a run-a test-a validate-a all-scenarios-a

PYTHON := .venv/bin/python
PIP := .venv/bin/pip

help:
	@echo "setup-a          Crear entorno e instalar dependencias de A"
	@echo "run-a            Ejecutar una simulación BASE"
	@echo "test-a           Ejecutar pruebas de A"
	@echo "validate-a       Validar la salida BASE de A"
	@echo "all-scenarios-a  Ejecutar todos los escenarios de A"

setup-a:
	python3 -m venv .venv
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
	ps-b logs-b sim-b topics-b describe-b evidence-b smoke-b test-b reset-b

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
	@echo "test-b           Ejecutar las pruebas de B"
	@echo "reset-b          Borrar el volumen del broker (destructivo)"

setup-b:
	$(PIP) install -r producers/requirements.txt

env-b:
	@test -f infra/.env || cp infra/.env.example infra/.env
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

test-b:
	cd producers && ../$(PYTHON) -m unittest discover -s tests -v

reset-b: env-b
	@echo "Esto borra el volumen del broker y todos los eventos publicados."
	@printf "Escribe 'si' para continuar: "; read answer; [ "$$answer" = "si" ]
	$(COMPOSE_FLINK_B) down -v
	rm -rf infra/checkpoints infra/savepoints
