# Parte B — Kafka, topics y publicación

## Diseño y alcance

B es la frontera entre el simulador y el procesamiento: recibe el sobre de
transporte de A, lo convierte en el evento contractual completo y lo publica en
el topic que corresponde según `contracts/topics.yaml`.

- `infra/compose.yaml`: Kafka en modo KRaft, PostgreSQL como event store, y
  consola web y simulador de A bajo perfiles opcionales.
- `infra/compose.flink.yaml`: JobManager y TaskManager sobre la misma red.
- `infra/scripts/`: creación idempotente de topics, comparación contra el
  contrato y prueba de humo de extremo a extremo.
- `producers/`: contrato, validación en tres pasos, enriquecimiento,
  particionado, los cinco canales, la reproducción del JSONL y el consumidor
  hacia PostgreSQL.

Lo pendiente por acuerdo con el equipo: el sink de persistencia de C y el
servicio del dashboard de D.

## Decisiones técnicas

### Enrutamiento por `event_type`, no por `source`

`source` y `source_hint` comparten los mismos cinco valores, así que el mapeo
entre ambos es la identidad. Lo que **no** es identidad es la relación con el
topic: el destino lo decide `event_type`. Un evento con `source = WEB` puede
terminar en `user-events`, `purchase-events` o `system-events`. Por eso no hay
"un producer por fuente": hay un enrutador por tipo de evento.

Si `source_hint` llega ausente o con un valor fuera del enum, el evento va al
`dead-letter`. Nunca se asume `WEB` por defecto: una fuente inventada
contaminaría las audiencias que calcula C.

### Particionador `murmur2_random`

El particionador por defecto de librdkafka es `consistent_random`, que usa
CRC32. El de los clientes Java es murmur2. Si dos productores del mismo sistema
usan particionadores distintos, un mismo `user_id` se parte entre particiones y
se pierde el orden por usuario, que es justamente la garantía que necesita C
para agregar por sesión.

El producer se configura con `partitioner=murmur2_random` y
`producers/partitioning.py` reimplementa murmur2 para poder anticipar la
partición. La prueba de humo compara esa predicción contra la partición que
informa el broker en cada acuse de entrega: si ambas coinciden para varias
claves repartidas entre las cuatro particiones de `user-events`, queda
demostrado que el particionado es el esperado.

### Librería: `confluent-kafka`

Frente a `kafka-python`, dos razones concretas:

1. **Los nombres de configuración coinciden con la documentación oficial del
   broker.** `acks`, `linger.ms`, `batch.size`, `compression.type` y
   `enable.idempotence` se escriben igual en el código, en `infra/.env` y en la
   documentación de Apache Kafka. `kafka-python` los renombra al estilo Python
   (`acks`, `linger_ms`, `max_batch_size`), lo que obliga a traducir cada
   parámetro mentalmente al comparar contra la referencia.
2. **Los callbacks de entrega por mensaje son necesarios para la evidencia del
   failover.** Cada `produce()` registra un `on_delivery` que recibe el acuse
   individual del broker con topic, partición y offset, o el error. Eso permite
   contar *publicados* contra *confirmados* y demostrar cuántos mensajes
   sobrevivieron a una caída del broker. Sin acuses por mensaje solo se sabe si
   la tanda completa falló.

**`poll()` y `flush()`.** `confluent-kafka` es asíncrono: `produce()` encola el
mensaje en un buffer interno de librdkafka y regresa de inmediato, sin haber
hablado con el broker. Los callbacks de entrega no se ejecutan solos: corren en
el hilo de la aplicación cuando esta cede el control.

- `poll(0)` atiende los acuses ya recibidos y regresa sin bloquear. Se llama
  después de cada `produce()` para que los callbacks se ejecuten a medida que
  llegan y el buffer no crezca sin control.
- `flush(timeout)` bloquea hasta que se confirme todo lo encolado y devuelve
  cuántos mensajes quedaron pendientes. Devolver algo distinto de cero
  significa pérdida de datos. Es obligatorio antes de terminar el proceso: sin
  `flush()`, salir del programa descarta el buffer en silencio.

### Almacenamiento y benchmarks

El log del broker usa un volumen nombrado en vez de un bind-mount. En Docker
Desktop los bind-mounts pasan por virtiofs y el sobrecosto de I/O se mezcla con
lo que se quiere medir. Los bind-mounts se reservan para lo que hay que
inspeccionar desde el host: salida del simulador, checkpoints y savepoints.

### Validación en tres pasos

`event_id` y `source` son obligatorios en el evento publicado, pero los genera
B. Validar el contrato completo contra la entrada mandaría el 100 % de los
eventos al `dead-letter`, así que el orden importa: primero se valida lo que
entrega A (nueve campos más el payload que exige el `event_type`), después se
enriquece, y solo al final se valida el evento de trece campos.

Las tablas de validación no están escritas a mano. `event.schema.json` liga
cada `event_type` con un `$ref` a `$defs` mediante sus ramas `allOf`, así que
los campos obligatorios de los doce payloads se leen del contrato. Lo mismo con
los enums, el `const` de `schema_version` y la lista de campos requeridos. Si
alguien cambia el contrato, las pruebas de B fallan solas en vez de divergir en
silencio.

El paso 3 no usa una librería de JSON Schema: comprueba las trece claves
exactas (`additionalProperties: false` incluido), los enums, el `const` y que
ambos timestamps sean ISO-8601 con zona horaria. Los payloads por tipo ya
quedaron cubiertos en el paso 1, así que agregar la dependencia no habría
comprado nada.

### Los cinco canales son datos, no subclases

Entre un producer WEB y uno IOT solo cambian dos cosas: el `source` y el perfil
de latencia. Cinco subclases que únicamente redefinen constantes son cinco
lugares donde olvidar un cambio, así que los canales son un diccionario de
`ChannelConfig` y hay una sola clase `BaseProducer`.

WEB y MOBILE concentran el 93 % del volumen y esperan 20 ms para agrupar
mensajes. POS es transaccional y espera 5 ms. IOT y VEHICLE son telemetría de
goteo: hacerlos esperar no llena el lote, solo agrega latencia.

### Contadores y `flush()`

Los contadores salen de los callbacks de entrega, uno por mensaje:
`publicados` son los que se encolaron, `enviados` los que el broker confirmó, y
la diferencia entre ambos es exactamente lo que se perdió. `rechazados` son los
que fueron al `dead-letter` por validación y `fallidos` los que el broker
rechazó.

`BaseProducer` es un context manager por una razón concreta: salir del proceso
sin llamar a `flush()` descarta el buffer de librdkafka sin aviso, y el
programa termina reportando éxito con mensajes que nunca salieron.

### Event store en PostgreSQL

Es el rastro de auditoría de B: qué se publicó, cuándo y en qué partición. No
es el sink de C, que sigue pendiente de acordar.

El consumidor usa `group.id = event-store`, distinto del que use Flink. Con
grupos distintos ambos reciben el flujo completo; con el mismo grupo se
repartirían las particiones y cada uno vería la mitad de los eventos.

Escribe en lotes de 500 filas o 2 segundos, lo que ocurra primero, y confirma
los offsets **después** de que la transacción de PostgreSQL termina. El orden
inverso perdería datos ante una caída entre el commit de offsets y la
escritura. Como la entrega es at-least-once, el reproceso está previsto:
`event_id` es la clave primaria y el insert lleva
`ON CONFLICT (event_id) DO NOTHING`.

Dos detalles del esquema: `payload` es `JSONB`, lo que permite consultar dentro
del evento sin desnormalizar (`payload->>'device'`); y las coordenadas de Kafka
van como `kafka_topic`, `kafka_partition` y `kafka_offset` porque `offset` y
`partition` son palabras reservadas en SQL.

El índice sobre esas coordenadas **no** es único a propósito: un segundo índice
único produciría un conflicto que `ON CONFLICT (event_id)` no captura, y una
sola fila repetida tumbaría el lote entero.

La tabla `runs` registra cada corrida de carga con sus cuatro contadores. La
escribe `run.py` al terminar; si PostgreSQL no está levantado, avisa y sigue,
porque publicar en Kafka no debe depender de la base de auditoría.

### Sin autocreación de topics

`auto.create.topics.enable=false`. Con la autocreación activada, un nombre mal
escrito produce un topic nuevo con una sola partición y el contrato se rompe en
silencio; el síntoma aparecería recién en las métricas de C. Apagada, el envío
falla de inmediato con un error explícito.

## Procedimiento reproducible

```bash
make setup-b
make env-b
make up-b                          # Kafka y PostgreSQL
make topics-b                      # topics del contrato
make describe-b                    # contraste contra el contrato
make smoke-b                       # ida y vuelta por los cinco topics
make produce-b LIMIT=2000 RATE=1000 # publica desde simulator/output
make store-b                       # consume hacia PostgreSQL (Ctrl-C)
make count-b                       # qué quedó almacenado
make test-b                        # 102 pruebas, sin broker
```

Evidencia archivada: `make evidence-b` deja el estado real de los topics en
`artifacts/parte-b/topics.json` (ruta ignorada por git, como indica la
convención del `.gitignore`).

## Resultados medidos

Corrida de 2000 eventos del escenario BASE a 1000 ev/s sobre un solo broker:

| Métrica | Valor |
|---|---|
| Publicados / enviados | 2000 / 2000 |
| Rechazados / fallidos | 0 / 0 |
| Tasa efectiva | 983,3 ev/s |
| Reparto por canal | WEB 939, MOBILE 919, POS 136, IOT 3, VEHICLE 3 |

Particionado: en la prueba de humo, las 25 claves cayeron en la partición que
predijo el particionador murmur2, repartidas entre las cuatro de
`user-events`.

Validación: con un archivo de seis líneas preparado con cinco defectos
distintos, se publicó 1 evento y se rechazaron 5, cada uno con su motivo en el
`dead-letter`: `source_hint` fuera del contrato, falta `event_type`, JSON
inválido, `event_timestamp` vacío y `PURCHASE.items` vacío.

Event store: 2024 filas almacenadas en lotes de 500 y un último lote parcial
por vencimiento de la ventana. Al releer todo el flujo con otro `group.id`, las
2024 filas se detectaron como duplicadas y se insertaron 0, lo que confirma la
deduplicación por `event_id`. El apagado con SIGINT vació el lote pendiente
antes de cerrar.

## Anexo: correcciones y acuerdos sobre el contrato

`contracts/` es de solo lectura para B. Lo que sigue son decisiones tomadas por
el equipo que **no** están escritas en el contrato v1.0 y que se documentan
aquí para no modificarlo.

### 1. Contrato del `dead-letter`

`contracts/` define el evento válido, pero no la forma del mensaje rechazado.
Acordado:

```json
{
  "error_reason": "source_hint fuera del contrato: 'SMARTWATCH'",
  "rejected_at": "2026-07-28T22:41:07.512+00:00",
  "original": { "source_hint": "SMARTWATCH", "event": { "...": "tal como llegó" } }
}
```

`original` es el sobre completo sin modificar, para poder reprocesar.
`rejected_at` usa el mismo formato que `ingestion_timestamp` (UTC con
milisegundos).

### 2. Excepción a la clave de partición

La regla general es `user_id` como clave en todos los envíos. Se corrige para
el `dead-letter`, que es la única excepción: se usa `user_id` si existe y es
una cadena no vacía, y `None` en caso contrario. El motivo es directo: uno de
los rechazos típicos es precisamente que `user_id` falte o venga mal, y en ese
caso no hay clave que usar. Con una sola partición el reparto es indistinto.

### 3. Orden de validación

`event_id` y `source` son obligatorios en el evento publicado, pero los genera
B. Exigirlos en la entrada mandaría todos los eventos al `dead-letter`. El
orden correcto es:

1. validar lo que entrega A: nueve campos más el payload según `event_type`;
2. enriquecer con los cuatro campos de B;
3. validar el evento completo de trece campos contra `event.schema.json`.

### 4. Ausencia de `event_type`

Las doce ramas `if` de `event.schema.json` no declaran
`required: ["event_type"]`. Un `if` sobre una propiedad ausente se evalúa como
verdadero, así que un evento sin `event_type` activa las doce ramas a la vez y
el validador produce doce fallos simultáneos ilegibles. No se corrige el
contrato: B detecta la ausencia de `event_type` antes de invocar al validador y
escribe el motivo del rechazo.

### 5. Divergencias menores entre documentos

- El formato de `event_id` aparece de tres formas: "UUID" en
  `producers/README.md`, `evt_<uuid4hex>` en el adaptador de ejemplo de A y
  `evt_00000001` en `contracts/sample_events.jsonl`. Se adopta
  `evt_<uuid4hex>`: el contador secuencial no funciona con varios productores
  en paralelo.
- `ingestion_timestamp` aparece en `-05:00` en las muestras y en UTC en el
  adaptador de ejemplo. Se adopta **UTC con milisegundos**, que hace evidente
  la divergencia con `event_timestamp`, que llega en `-05:00`.
- `topics.yaml` describe `system-events` como topic de eventos de control
  pendientes de contrato, pero hoy recibe `SOCIAL_POST`, que sí está
  formalizado. El uso real no coincide con la nota.

## Dificultades y limitaciones

- **Tiempo de evento contra tiempo real.** El reloj virtual de A arranca el
  25-jul-2026 y avanza a 3600×. El mensaje de Kafka lleva `CreateTime` real de
  publicación; poner el tiempo virtual haría que los eventos nacieran fuera de
  la ventana de retención. C debe extraer `event_timestamp` del JSON para sus
  watermarks.
- **Un solo broker.** Con replicación 1 no hay tolerancia a fallos real. La
  evidencia de failover se limita a demostrar el conteo publicados contra
  confirmados durante un reinicio del broker.
- **Persistencia de C sin definir.** El event store de B no la reemplaza: son
  cosas distintas. El sink de Flink lo decide C.
- **Dashboard pendiente.** Se suma cuando D publique su servicio; la red
  `audiencias` ya tiene nombre fijo para que pueda unirse como externa.
- **PostgreSQL 18 cambió el punto de montaje.** El volumen va en
  `/var/lib/postgresql`, no en `/var/lib/postgresql/data`: montarlo en el
  subdirectorio deja el cluster en un estado que la imagen rechaza al arrancar.
- **El `dead-letter` no se archiva.** El event store consume solo los cuatro
  topics de negocio, porque el wrapper de rechazo tiene otra forma que las
  trece columnas de la tabla. Los rechazos quedan en el topic.

## Contribución individual

Infraestructura Kafka en KRaft con doble listener, creación idempotente de
topics derivada del contrato, particionador compatible con clientes Java,
validación en tres pasos con las tablas leídas del propio contrato, los cinco
canales de publicación con contadores por acuse de entrega, reproducción del
JSONL a tasa controlada, event store en PostgreSQL con deduplicación y commit
de offsets tras la escritura, contrato del `dead-letter`, scripts de
verificación y evidencia, y 102 pruebas unitarias que corren sin broker ni base
de datos.
