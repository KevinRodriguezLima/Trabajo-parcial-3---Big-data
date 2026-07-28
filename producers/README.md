# Parte B — Producers

Espacio para adaptadores por fuente: WEB, MOBILE, IOT, VEHICLE y POS.

Contrato de entrada:

```json
{"source_hint": "WEB", "event": {"event_type": "LOGIN"}}
```

Responsabilidades:

1. Validar el mensaje recibido de A.
2. Agregar UUID `event_id`, `schema_version = "1.0"`,
   `ingestion_timestamp` real y `source`.
3. Conservar `event_timestamp`.
4. Serializar, aplicar batching, `acks` y reintentos.
5. Usar `user_id` como key y enrutar con `../contracts/topics.yaml`.
6. Enviar mensajes inválidos a `dead-letter`.

`simulator/examples/producer_adapter_stub.py` sirve como ejemplo conceptual,
pero el responsable de B decide lenguaje, librería y organización final.
