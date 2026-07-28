# Parte B — Kafka, topics y publicación

## Diseño y alcance

B es la frontera entre el simulador y el procesamiento: recibe el sobre de
transporte de A, lo convierte en el evento contractual completo y lo publica en
el topic que corresponde según `contracts/topics.yaml`.

Esta entrega cubre la infraestructura y la verificación:

- `infra/compose.yaml`: Kafka en modo KRaft, un solo nodo, con consola web y el
  simulador de A bajo perfiles opcionales.
- `infra/compose.flink.yaml`: JobManager y TaskManager sobre la misma red.
- `infra/scripts/`: creación idempotente de topics, comparación contra el
  contrato y prueba de humo de extremo a extremo.
- `producers/schema.py`, `producers/partitioning.py` y `producers/envelope.py`:
  contrato, enrutamiento, particionado y enriquecimiento como funciones puras.

La lectura de los JSONL a tasa controlada (`producers/run.py`), la validación
completa contra `event.schema.json` y el envío al `dead-letter` en producción
son la fase siguiente.

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

### Sin autocreación de topics

`auto.create.topics.enable=false`. Con la autocreación activada, un nombre mal
escrito produce un topic nuevo con una sola partición y el contrato se rompe en
silencio; el síntoma aparecería recién en las métricas de C. Apagada, el envío
falla de inmediato con un error explícito.

## Procedimiento reproducible

```bash
make setup-b
make env-b
make up-b
make topics-b
make describe-b
make smoke-b
make test-b
```

Evidencia archivada: `make evidence-b` deja el estado real de los topics en
`artifacts/parte-b/topics.json` (ruta ignorada por git, como indica la
convención del `.gitignore`).

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
- **Persistencia sin definir.** El motor depende del sink que elija C; el
  `compose.yaml` todavía no lo incluye.
- **Dashboard pendiente.** Se suma cuando D publique su servicio; la red
  `audiencias` ya tiene nombre fijo para que pueda unirse como externa.

## Contribución individual

Infraestructura Kafka en KRaft con doble listener, creación idempotente de
topics derivada del contrato, particionador compatible con clientes Java,
enriquecimiento del sobre, contrato del `dead-letter`, scripts de verificación
y evidencia, y 41 pruebas unitarias que corren sin broker levantado.
