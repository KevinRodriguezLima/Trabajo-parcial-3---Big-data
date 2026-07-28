# Parte B — Infraestructura

Kafka en modo KRaft, creación idempotente de los topics del contrato y los
scripts de verificación que dejan evidencia para el informe.

La frontera con el resto del equipo son JSON y `../contracts/`. Nada de aquí
importa código de `../simulator/`.

## Puesta en marcha

```bash
make setup-b      # dependencias de B en el .venv compartido
make env-b        # copia infra/.env.example a infra/.env
make up-b         # levanta el broker y el event store
make topics-b     # crea los topics del contrato
make describe-b   # compara lo real contra el contrato
make smoke-b      # publica y consume un evento por topic
```

`make help-b` lista todos los comandos.

## Cómo conectarse

El broker publica **dos listeners de datos** porque hay dos mundos distintos:

| Desde | Bootstrap | Quién |
|---|---|---|
| Dentro de la red `audiencias` | `kafka:9092` | Flink, dashboard |
| Desde el host | `localhost:29092` | `producers/`, `infra/scripts/` |

Con un solo listener, `advertised.listeners` queda correcto para uno de los dos
y el otro falla al refrescar metadatos: conecta, recibe una dirección que no
resuelve y se cae en el primer envío.

## Decisiones del broker

**`auto.create.topics.enable=false`.** Con la autocreación activada, un nombre
de topic mal escrito crea el topic al vuelo con una sola partición y el
particionado del contrato se rompe sin que nadie se entere hasta ver las
métricas de C. Apagada, el error es inmediato y explícito. Por lo mismo,
`num.partitions=1`: si alguna ruta se saltara el control, que no herede un
número plausible.

**Factores de replicación en 1.** Obligatorio con un solo broker. Los valores
por defecto de los topics internos (`__consumer_offsets`,
`__transaction_state`) son 3, y con un nodo el broker no puede elegir líder y
arranca a medias.

**`CLUSTER_ID` fijo en `infra/.env`.** Si se deja al azar, cada recreación del
volumen deja metadatos KRaft que no corresponden al log almacenado.

**Retención por defecto (7 días).** No hay problema aunque `event_timestamp`
sea del 25-jul-2026 y avance a 3600×, porque el mensaje de Kafka lleva
`CreateTime` real de publicación. C extrae el tiempo de evento del JSON.

## Almacenamiento

El log del broker vive en un **volumen nombrado** (`audiencias-kafka-data`), no
en un bind-mount: en Docker Desktop los bind-mounts pasan por virtiofs y el
sobrecosto de I/O contamina las cifras de las corridas de carga.

Los directorios que sí son bind-mount son los que C necesita inspeccionar desde
el host, y el `.gitignore` de la raíz ya los contempla:

```text
infra/data/         salida del simulador cuando corre bajo el profile sim
infra/checkpoints/  checkpoints de Flink
infra/savepoints/   savepoints de Flink
```

## Perfiles

El stack base solo levanta el broker. Lo demás va bajo perfiles para que no
compita por CPU ni RAM durante los benchmarks:

```bash
make up-tools-b   # profile tools: consola web en localhost:8080
make sim-b        # profile sim: simulador de A escribiendo en infra/data
make up-flink-b   # compose.flink.yaml: JobManager y TaskManager
```

El profile `sim` construye la imagen de `../simulator` sin modificar su código
y monta `./data/simulator-output`. El simulador no habla con Kafka: escribe
JSONL y `producers/` los lee después.

## Flink

`compose.flink.yaml` es un override, siempre se usa junto a `compose.yaml`
(`make up-flink-b` ya lo hace). Monta `../flink-jobs` en `/opt/flink/jobs` en
**solo lectura**, y los checkpoints y savepoints en `infra/`.

La red se llama `audiencias` con nombre fijo, así que cuando D publique el
dashboard puede declararla `external: true` desde su propio proyecto Compose y
alcanzar `kafka:9092` sin tocar estos archivos.

En Linux, si el JobManager no puede escribir los checkpoints, hay que dar
permiso al uid del contenedor: `sudo chown -R 9999:9999 infra/checkpoints
infra/savepoints`. En Docker Desktop no hace falta.

## Scripts

Todos aceptan `--bootstrap-servers` y `--timeout`, y leen `infra/.env` como
respaldo. Salen con código distinto de cero si algo no cuadra, para poder
encadenarlos en una verificación.

- `create_topics.py` — lee `../contracts/topics.yaml` como única fuente de
  verdad. Crea lo que falta y no toca lo que ya coincide. Si un topic existe
  con otro número de particiones, lo reporta y **no lo modifica**: bajar
  particiones es imposible en Kafka y subirlas rompe el orden por clave de lo
  ya publicado. Eso se resuelve con `make reset-b`. Admite `--dry-run`.
- `describe_topics.py` — estado real contra contrato, con líderes, réplicas e
  ISR por partición. Con `--json` deja el reporte como evidencia.
- `smoke_test.py` — publica un evento por topic de negocio más uno al
  `dead-letter`, verifica que la partición que informa el broker coincide con
  la que calcula el particionador por `user_id`, y consume todo de vuelta.

El mapa de enrutamiento no vive aquí: está en `../producers/schema.py`,
derivado de `topics.yaml`. Estos scripts lo importan, nunca al revés.

## Event store

`postgres` guarda lo que se publicó: es el rastro de auditoría de B, no el sink
de C. `init-db.sql` crea las tablas `events` y `runs` y solo corre cuando el
volumen está vacío, así que el SQL es idempotente.

El volumen se monta en `/var/lib/postgresql`, no en `/var/lib/postgresql/data`:
desde Postgres 18 montar el subdirectorio deja el cluster en un estado que la
imagen rechaza al arrancar.

```bash
make store-b   # consume hacia PostgreSQL (Ctrl-C vacía el lote y cierra)
make count-b   # filas por topic y últimas corridas
make psql-b    # consola SQL
```

## Pendientes acordados

- **Sink de Flink**: lo define C. El event store de B no lo reemplaza.
- **Dashboard**: pendiente hasta que D publique su servicio.
