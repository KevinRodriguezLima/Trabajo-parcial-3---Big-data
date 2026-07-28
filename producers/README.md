# Parte B — Producers

Convierte el sobre de transporte de A en el evento contractual y lo publica en
el topic que le toca. No importa nada de `../simulator/`: la frontera son los
JSONL y `../contracts/`.

## Uso

```bash
make produce-b LIMIT=2000 RATE=1000     # publica desde simulator/output
make store-b                            # consume hacia PostgreSQL (Ctrl-C)
make count-b                            # qué quedó almacenado
```

Directo:

```bash
.venv/bin/python producers/run.py --file simulator/output/base/events.jsonl \
  --bootstrap localhost:29092 --rate 500 --limit 10000
.venv/bin/python producers/consumer_store.py --group-id event-store
```

## Validación en tres pasos

`event_id` y `source` son obligatorios en el evento publicado pero los genera
B, así que no pueden exigirse en la entrada. Invertir el orden mandaría todo al
`dead-letter`.

1. `validate_input(sobre)` — los nueve campos de A más el payload que exige el
   `event_type`. La ausencia de `event_type` se detecta primero: sin él, las
   doce ramas `if` del contrato se activan a la vez y el error sale ilegible.
2. `enrich(sobre)` — agrega `event_id`, `schema_version`,
   `ingestion_timestamp` y `source`; descarta `source_hint`.
3. `validate_event(evento)` — las trece claves contra `event.schema.json`:
   nada de más, nada de menos, enums válidos y timestamps con zona horaria.

Lo que falla en cualquier paso va al `dead-letter` con el sobre original
intacto. Nunca se descarta en silencio.

## Módulos

| Archivo | Qué hace | Necesita broker |
|---|---|---|
| `schema.py` | contrato, `TOPIC_BY_EVENT`, enrutamiento | no |
| `validation.py` | pasos 1 y 3, derivados de `event.schema.json` | no |
| `envelope.py` | paso 2 y wrapper del `dead-letter` | no |
| `partitioning.py` | murmur2, compatible con clientes Java | no |
| `channels.py` | los cinco canales y su perfil de latencia | no |
| `store.py` | filas y lotes del event store | no |
| `base.py` | `BaseProducer`: publicación y contadores | sí |
| `run.py` | CLI de reproducción del JSONL | sí |
| `consumer_store.py` | consumidor hacia PostgreSQL | sí |

Las tablas de validación y enrutamiento no están escritas a mano: salen de
`../contracts/`. Si el contrato cambia, las pruebas fallan solas.

## Los cinco canales

Un `BaseProducer` por fuente. Lo único que cambia entre ellos es `source` y el
perfil de latencia, así que son datos y no subclases:

| Canal | linger.ms | batch.size | Por qué |
|---|---|---|---|
| WEB, MOBILE | 20 | 256 KiB | 93 % del volumen; conviene agrupar |
| POS | 5 | 64 KiB | transaccional |
| IOT, VEHICLE | 0 | 16 KiB | goteo: esperar no llena el lote |

`source` **no** decide el topic; lo decide `event_type`. Un canal WEB publica
en `user-events`, `purchase-events` y `system-events`.

## Contadores

Salen de los callbacks de entrega, uno por mensaje:

- `publicados`: aceptados y encolados hacia un topic de negocio.
- `enviados`: con acuse del broker. La diferencia con `publicados` es lo que
  se perdió.
- `rechazados`: fueron al `dead-letter` por validación.
- `fallidos`: el broker rechazó la entrega.

`BaseProducer` es un context manager porque salir sin `flush()` descarta el
buffer de librdkafka en silencio.

## Event store

`consumer_store.py` guarda en PostgreSQL lo que se publicó. Es el rastro de
auditoría de B, no el sink de C, y por eso usa un `group.id` propio
(`event-store`): con grupos distintos ambos reciben el flujo completo en vez
de repartírselo.

Escribe en lotes de 500 filas o 2 segundos, lo que ocurra primero, y confirma
los offsets **después** de escribir. Si el proceso muere en medio, reprocesa y
`ON CONFLICT (event_id) DO NOTHING` descarta lo repetido.
