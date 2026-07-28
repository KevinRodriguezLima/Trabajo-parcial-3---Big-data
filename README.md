# Proyecto Final 3 — Plataforma de Audiencias Digitales en Tiempo Real

Trabajo para simular actividad digital, transportar eventos con Kafka,
procesarlos con Apache Flink y visualizar audiencias y métricas en tiempo real.

La estructura sigue el flujo definido en la guía del proyecto:

```text
Simulador de agentes → Producers → Kafka → Flink → Dashboard
                              └──── persistencia / alertas ────┘
```

## Estado por componente

| Responsable          | Carpeta                       | Estado                 |
| -------------------- | ----------------------------- | ---------------------- |
| Simulador de agentes | `simulator/`                  | Implementado y probado |
| Kafka y producers    | `infra/`, `producers/`        | Estructura preparada   |
| Procesamiento Flink  | `flink-jobs/`                 | Estructura preparada   |
| Dashboard e informe  | `dashboard/`, `docs/reports/` | Estructura preparada   |

Los directorios B, C y D contienen únicamente acuerdos de integración y
orientación. Cada responsable puede elegir su implementación sin que A invada
su trabajo.

## Estructura

```text
.
├── contracts/          Contrato de eventos, topics y muestras compartidas
├── simulator/          Parte A: agentes, escenarios, catálogo y salida JSONL
├── infra/              Parte B: infraestructura local y Kafka
├── producers/          Parte B: adaptadores y publicación
├── flink-jobs/         Parte C: limpieza, métricas, audiencias y alertas
├── dashboard/          Parte D: backend en tiempo real y visualización
├── docs/
│   ├── reference/      Documentos originales del encargo
│   └── reports/        Secciones del informe aportadas por cada integrante
├── Makefile            Comandos comunes del monorepo
└── .env.example        Variables compartidas, sin secretos
```

## Inicio rápido

La Parte del simulador se puede ejecutar sin Kafka:

```bash
make setup-a
make test-a
make run-a
```

La salida aparece en `simulator/output/base/`. Para parámetros personalizados:

```bash
cd simulator
../.venv/bin/python run.py \
  --scenario BLACK_FRIDAY \
  --agents 500 \
  --duration 60 \
  --speed 3600 \
  --no-console
```

La documentación completa del simulador está en [simulator/README.md](simulator/README.md).

## Acuerdo de integración

1. A genera `source_hint` y el objeto `event` con los campos que le corresponden.
2. B agrega `event_id`, `schema_version`, `ingestion_timestamp` y `source`.
3. B usa `user_id` como clave de partición y enruta según
   [contracts/topics.yaml](contracts/topics.yaml).
4. C consume el evento completo, trabaja con `event_timestamp` y publica
   resultados con los contratos que acuerde con D.
5. D consume esas salidas sin depender de clases internas de A, B o C.

El contrato compartido es la frontera entre módulos. Cualquier cambio requiere
acuerdo del equipo y aumento de `schema_version`.
