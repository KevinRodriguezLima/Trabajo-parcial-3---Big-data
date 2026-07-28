# Parte A — Simulador de agentes

## Diseño

Se implementó un simulador concurrente en Python basado en ocho agentes
conductuales configurables. Cada usuario ejecuta una máquina de estados finita
y utiliza un reloj virtual acelerado para conservar semántica de tiempo del
evento.

## Decisiones técnicas

- Configuración de perfiles y escenarios en YAML.
- Semillas independientes para mantener ejecuciones reproducibles.
- Payloads denormalizados de compra para facilitar agregaciones en Flink.
- Separación entre los campos generados por A y el enriquecimiento de B.
- Archivos JSONL consolidados y por fuente para pruebas sin Kafka.

## Validación

Las pruebas comprueban los ocho perfiles, los doce contratos, la generación
JSONL, el rechazo de parámetros inválidos y la propagación de errores de tareas
asíncronas. `scripts/validate_output.py` revisa todos los eventos generados.

## Integración

La interfaz de A hacia B es `GeneratedMessage`, serializada con `source_hint` y
`event`. B completa el sobre conforme a `../../contracts/event.schema.json` y
publica usando el mapa de `../../contracts/topics.yaml`.

## Limitaciones

El simulador no administra Kafka, no crea campos propios de productores y no
define señales de control que no estén formalizadas en el contrato v1.0.
