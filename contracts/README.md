# Contratos compartidos

Archivos:

- `event.schema.json`: esquema JSON del evento ya enriquecido por B.
- `topics.yaml`: nombres, particiones y reglas de enrutamiento acordadas.
- `sample_events.jsonl`: muestras completas para desarrollar consumidores.
- `contratos.md`: responsabilidades y decisiones del contrato v1.0.

A produce los campos de negocio y un `source_hint` externo al evento. B convierte
ese mensaje interno en el evento contractual completo. `source_hint` no se
publica como parte del esquema final.

No se debe cambiar un campo, enum, topic o número de particiones sin coordinarlo
con todos los integrantes.
