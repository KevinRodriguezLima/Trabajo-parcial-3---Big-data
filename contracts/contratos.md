# Contrato de eventos v1.0

Todo evento publicado en Kafka utiliza un sobre común y un `payload` dependiente
de `event_type`.

## Responsabilidad por campos

| Campo | Responsable |
|---|---|
| `event_type`, `event_timestamp` | A — Simulador |
| `user_id`, `session_id`, `agent_profile` | A — Simulador |
| `city`, `region`, `scenario`, `payload` | A — Simulador |
| `event_id`, `schema_version` | B — Productor |
| `ingestion_timestamp`, `source` | B — Productor |

`event_timestamp` es tiempo virtual del evento y nunca debe ser reemplazado por
el productor. `ingestion_timestamp` es tiempo real de publicación.

## Tipos

`LOGIN`, `SEARCH`, `PAGE_VIEW`, `VIEW_PRODUCT`, `ADD_TO_CART`,
`REMOVE_FROM_CART`, `PURCHASE`, `PAYMENT_FAILED`, `GPS_UPDATE`,
`IOT_READING`, `MOTION_DETECTED` y `SOCIAL_POST`.

Los payloads exactos están formalizados en `event.schema.json` y ejemplificados
en `sample_events.jsonl`.

## Reglas transversales

- `user_id` es la clave de partición.
- Eventos inválidos se envían a `dead-letter`.
- El procesamiento usa tiempo del evento.
- Una modificación incompatible requiere una nueva versión del esquema.
- Los cambios de escenario y señales de control necesitan un contrato propio
  antes de implementarse; v1.0 no define su payload.
