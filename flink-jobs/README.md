# Parte C — Procesamiento Flink

Implementación del módulo de procesamiento en streaming para la plataforma de audiencias digitales utilizando **PyFlink**.

## Alcance Implementado

1. **Validación, Limpieza y Enriquecimiento**:
   - Validación contra `contracts/event.schema.json` (v1.0).
   - Deduplicación basada en `event_id`.
   - Enriquecimiento con latencia (`latency_ms`) y marca de tiempo de procesamiento (`processing_timestamp`).
   - Envío de eventos inválidos o duplicados al topic `dead-letter`.

2. **Métricas en Ventanas Configurables**:
   - **Throughput**: Eventos por segundo y conteo total por ventana.
   - **Active Users**: Conteo de usuarios únicos en ventana.
   - **Events By Type**: Distribución por `event_type`.
   - **Top Products**: Ranking de los 10 productos más vistos y más comprados.
   - **Purchases by Region**: Agregado de ventas y montos por región.
   - **Conversion Funnel**: Tasa de conversión `VIEW_PRODUCT -> ADD_TO_CART -> PURCHASE`.
   - **Trends**: Series de tiempo agregadas para gráficos de tendencias.

3. **Motor Pluggable de 7 Audiencias**:
   - `COMPRADOR_COMPULSIVO`: ≥3 compras en ventana.
   - `COMPARADOR_ACTIVO`: ≥5 vistas de productos distintos sin agregar al carrito.
   - `CARRITO_ABANDONADO`: Producto en carrito sin compra tras timeout.
   - `COMPRADOR_NOCTURNO`: ≥3 eventos en horario nocturno (22:00 - 06:00).
   - `USUARIO_ALTO_VALOR`: Compras acumuladas ≥ S/ 1000 PEN.
   - `NAVEGADOR_INDECISO`: ≥3 ciclos de agregar y quitar del carrito.
   - `USUARIO_MULTI_DISPOSITIVO`: Eventos registrados desde ≥2 fuentes distintas (`WEB`, `MOBILE`, etc.).
   - *Nota*: Las reglas y umbrales están centralizados en `src/config.py` y el registro de reglas es extensible (`AudienceClassifierRegistry`).

4. **Detección de Anomalías y Alertas**:
   - `TRAFFIC_SPIKE`: Disparo cuando el tráfico supera 3× la media móvil.
   - `TRAFFIC_DROP`: Alerta si el tráfico cae por debajo del 20% de la media móvil.
   - `HIGH_PAYMENT_FAILURE_RATE`: Alerta cuando la tasa de fallos de pago excede el 20%.
   - `HIGH_VALUE_CART`: Detección de carritos/compras inusualmente altos (≥ S/ 5000 PEN).
   - `HIGH_LATENCY`: Alerta si la latencia promedio supera los 30 segundos.

5. **Salidas Duales para Parte D**:
   - **Topics Kafka**: `metrics.*`, `audiences.classifications`, `alerts.anomalies`.
   - **Tablas PostgreSQL**: `flink_metrics`, `audience_classifications`, `alerts_anomalies` (disponibles en la BD `audiencias`).

## Estructura

```text
flink-jobs/
├── src/
│   ├── config.py           # Configuración de ventanas, umbrales y conexiones
│   ├── schemas.py          # Validación de contratos y utilidades de tiempo
│   ├── validation.py       # Deduplicación y limpieza
│   ├── sinks.py            # Publicación a PostgreSQL y Kafka
│   ├── main.py             # Entrypoint y orquestación del pipeline
│   ├── metrics/            # Módulos de métricas por ventana
│   ├── audiences/          # Motor pluggable de las 7 audiencias
│   └── alerts/             # Detector de anomalías
└── tests/                  # Pruebas unitarias
```

## Ejecución y Pruebas

```bash
make test-c     # Ejecutar suite de pruebas unitarias
make count-c    # Consultar estado de métricas/audiencias almacenadas en Postgres
```

