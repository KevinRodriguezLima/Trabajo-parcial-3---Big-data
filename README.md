# Proyecto Final 3 - Plataforma de Audiencias Digitales en Tiempo Real

Trabajo para simular actividad digital, transportar eventos con Kafka,
procesarlos con Apache Flink y visualizar audiencias y metricas en tiempo real.

La estructura sigue el flujo definido en la guia del proyecto:

```text
Simulador de agentes -> Producers -> Kafka -> Flink -> Dashboard
                              |---- persistencia / alertas ----|
```

## Estado por componente

| Responsable | Carpeta | Estado |
| --- | --- | --- |
| Simulador de agentes | `simulator/` | Implementado y probado |
| Kafka y producers | `infra/`, `producers/` | Implementado |
| Procesamiento Flink | `flink-jobs/` | Implementado con microventanas Kafka |
| Dashboard | `dashboard/` | Implementado con backend realtime |

## Estructura

```text
.
|-- contracts/          Contrato de eventos, topics y muestras compartidas
|-- simulator/          Parte A: agentes, escenarios, catalogo y salida JSONL
|-- infra/              Parte B: infraestructura local y Kafka
|-- producers/          Parte B: adaptadores y publicacion
|-- flink-jobs/         Parte C: limpieza, metricas, audiencias y alertas
|-- dashboard/          Parte D: backend realtime y visualizacion
|-- docs/
|   |-- reference/      Documentos originales del encargo
|   `-- reports/        Secciones del informe
|-- Makefile            Comandos comunes del monorepo
`-- .env.example        Variables compartidas, sin secretos
```

## Inicio rapido

La parte del simulador se puede ejecutar sin Kafka:

```bash
make setup-a
make test-a
make run-a
```

La salida aparece en `simulator/output/base/`. Para parametros personalizados:

```bash
cd simulator
../.venv/bin/python run.py \
  --scenario BLACK_FRIDAY \
  --agents 500 \
  --duration 60 \
  --speed 3600 \
  --no-console
```

La documentacion completa del simulador esta en [simulator/README.md](simulator/README.md).

## Ejecucion Conectada

Para levantar Kafka, PostgreSQL, Flink, producers y dashboard conectado:

```bash
python3 -m venv .venv
make setup-a setup-b setup-c setup-d
make up-flink-b
make topics-b
make run-a
make produce-b FILE=simulator/output/base/events.jsonl RATE=100
```

En una terminal separada, ejecutar el procesador continuo:

```bash
make stream-c
```

En otras dos terminales, levantar el backend realtime y el dashboard:

```bash
make backend-d
make dashboard-d
```

El dashboard queda disponible en `http://localhost:3000` y consume snapshots
desde `http://localhost:8000/events/dashboard`.

## Acuerdo de integracion

1. A genera `source_hint` y el objeto `event` con los campos que le corresponden.
2. B agrega `event_id`, `schema_version`, `ingestion_timestamp` y `source`.
3. B usa `user_id` como clave de particion y enruta segun
   [contracts/topics.yaml](contracts/topics.yaml).
4. C consume el evento completo, trabaja con `event_timestamp` y publica
   resultados en PostgreSQL y en los topics `metrics.*`,
   `audiences.classifications` y `alerts.anomalies`.
5. D consume las salidas de C mediante el backend realtime del dashboard.

El contrato compartido es la frontera entre modulos. Cualquier cambio requiere
acuerdo del equipo y aumento de `schema_version`.
