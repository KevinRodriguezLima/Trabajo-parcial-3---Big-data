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
