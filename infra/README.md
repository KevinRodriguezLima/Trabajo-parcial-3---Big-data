# Parte B — Infraestructura

Espacio del responsable de Kafka e infraestructura. No contiene una
implementación impuesta.

Entregables esperados:

- `compose.yaml` grupal con Kafka en modo KRaft, Flink, persistencia y dashboard.
- Creación idempotente de los topics definidos en `../contracts/topics.yaml`.
- Volúmenes, health checks y red interna.
- Configuración mediante variables de entorno, sin secretos versionados.
- Evidencia reproducible del flujo y de la carga.

La infraestructura no debe conocer clases internas de `simulator/`; su frontera
son JSON y los contratos compartidos.
