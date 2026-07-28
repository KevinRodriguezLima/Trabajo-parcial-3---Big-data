# Parte — Simulador de agentes

Eventos\*\*.

Implementa ocho perfiles configurables como máquinas de estado, un motor
concurrente con `asyncio`, reloj virtual acelerado, siete escenarios
empresariales, catálogo de productos y regiones del Perú, y los doce payloads
del contrato v1.0.

El [README principal](../README.md) explica el monorepo completo. El contrato
compartido se encuentra en [`../contracts/`](../contracts/).

## Responsabilidades

```json
{
  "event_type": "VIEW_PRODUCT",
  "event_timestamp": "2026-07-25T22:14:03.482-05:00",
  "user_id": "USR000254",
  "session_id": "SES_USR000254_0001",
  "agent_profile": "COMPARADOR",
  "city": "Arequipa",
  "region": "AREQUIPA",
  "scenario": "CYBER_MONDAY",
  "payload": {
    "product_id": "P001",
    "product_name": "Laptop Lenovo IdeaPad 3",
    "category": "TECNOLOGIA",
    "price": 2624.93,
    "dwell_time_ms": 8700
  }
}
```

La salida local se entrega a B mediante:

```json
{ "source_hint": "WEB", "event": { "...": "campos de A" } }
```

`source_hint` indica qué producer debe recibir el mensaje. B agrega `event_id`,
`schema_version`, `ingestion_timestamp` y `source`; nunca reemplaza
`event_timestamp`.

## Estructura

```text
simulator/
├── simulator/                  Paquete Python principal
│   ├── agent.py                Máquina de estados de cada usuario
│   ├── background.py           GPS, IoT, movimiento y redes sociales
│   ├── catalog.py              Productos, precios y ubicaciones
│   ├── clock.py                Reloj virtual acelerado
│   ├── config.py               Lectura de YAML
│   ├── engine.py               Motor concurrente
│   ├── event_factory.py        Construcción de los 12 payloads
│   ├── policy.py               Pesos y decisiones por perfil
│   ├── sinks.py                JSONL, consola y cola asíncrona
│   └── validation.py           Validación de la interfaz A → B
├── configs/
│   ├── simulation.yaml
│   ├── profiles.yaml
│   └── scenarios/
├── data/                       Catálogo y regiones
├── examples/                   Muestras y adaptador conceptual para B
├── scripts/                    Ejecución y validación
├── tests/                      Pruebas automáticas
├── docs/                       Arquitectura e informe de A
├── Dockerfile
├── docker-compose.simulator.yml
├── requirements.txt
└── run.py
```

## Máquina de estados

```text
OFFLINE ──LOGIN──> HOME
HOME ──SEARCH──> PRODUCT
HOME ──PAGE_VIEW──> HOME
PRODUCT ──VIEW_PRODUCT + ADD_TO_CART──> CART
PRODUCT ──VIEW_PRODUCT + SEARCH──> PRODUCT
CART ──ADD_TO_CART / REMOVE_FROM_CART──> CART
CART ──PURCHASE──> OFFLINE
CART ──PAYMENT_FAILED──> CART
HOME / PRODUCT / CART ──EXIT──> OFFLINE
```

Los ocho perfiles comparten los estados, pero usan probabilidades, horarios,
precios y fuentes diferentes:

- `COMPRADOR_COMPULSIVO`
- `COMPARADOR`
- `COMPRADOR_NOCTURNO`
- `CLIENTE_PREMIUM`
- `CLIENTE_FRECUENTE`
- `USUARIO_EXPLORADOR`
- `CLIENTE_INDECISO`
- `CLIENTE_ESTACIONAL`

## Instalación y pruebas

Desde la raíz del monorepo:

```bash
make setup-a
make test-a
make run-a
```

O directamente:

```bash
cd simulator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
python run.py --scenario BASE --agents 20 --duration 5 --speed 3600
```

Parámetros:

- `--scenario`: escenario activo.
- `--agents`: usuarios concurrentes.
- `--duration`: duración real en segundos.
- `--speed`: segundos virtuales por segundo real.
- `--output`: directorio base de salida.
- `--no-console`: suprime las muestras impresas.

## Escenarios

`BASE`, `NAVIDAD`, `CYBER_MONDAY`, `BLACK_FRIDAY`, `FIESTAS_PATRIAS`,
`CAMPANA_ESCOLAR` y `DIA_DEL_PADRE`.

Para ejecutar todos:

```bash
AGENTS=300 DURATION=30 SPEED=3600 ./scripts/run_all_scenarios.sh
```

## Salidas y validación

Cada escenario genera:

```text
output/<escenario>/events.jsonl
output/<escenario>/events_web.jsonl
output/<escenario>/events_mobile.jsonl
output/<escenario>/events_iot.jsonl
output/<escenario>/events_vehicle.jsonl
output/<escenario>/events_pos.jsonl
output/<escenario>/summary.json
```

Validación:

```bash
python scripts/validate_output.py output/base/events.jsonl
```

Las salidas se ignoran en Git porque pueden crecer rápidamente.

## Docker

```bash
docker compose -f docker-compose.simulator.yml build
SCENARIO=CYBER_MONDAY AGENTS=500 DURATION=60 SPEED=3600 \
  docker compose -f docker-compose.simulator.yml up
```

El compose de A es independiente para pruebas. B podrá incorporar el servicio
al `infra/compose.yaml` grupal sin modificar el código del simulador.

## Integración con B

B puede leer los JSONL por fuente o importar `AsyncQueueSink`. El archivo
`examples/producer_adapter_stub.py` muestra conceptualmente cómo:

1. recibir `GeneratedMessage`;
2. enriquecer el sobre;
3. validar contra `../contracts/event.schema.json`;
4. usar `user_id` como clave;
5. enrutar con `../contracts/topics.yaml`.

No se inventó un evento para cambios de escenario: el PDF menciona señales de
control en `system-events`, pero el contrato v1.0 no define tipo ni payload.
Añadirlo requiere acuerdo del equipo y una nueva versión.

## Documentación

- `docs/arquitectura_y_fsm.md`: arquitectura y diagramas de estados.
- `docs/parte_a_informe.md`: base de la sección que A aporta al informe final.
- `QUICKSTART.txt`: recordatorio de ejecución corta.
