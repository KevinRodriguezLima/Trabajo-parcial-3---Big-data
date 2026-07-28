# Parte C — Procesamiento Flink

Espacio del responsable de procesamiento. La estructura interna se decidirá
cuando se elija PyFlink, Java u otra opción compatible.

Alcance esperado:

- Validación, limpieza y enriquecimiento.
- Watermarks basados en `event_timestamp`.
- Ventanas para eventos/s, usuarios activos y tendencias.
- Agregaciones de productos, compras, regiones y conversión.
- Siete audiencias con estado, timers, reglas y umbrales documentados.
- Detección de anomalías y alertas.
- Publicación de salidas estables para D.

Antes de programar, C y D deben acordar contratos para `metrics.*`,
`audiences.*` y alertas. Esos contratos deben añadirse a `../contracts/` sin
modificar el evento v1.0 de entrada.
