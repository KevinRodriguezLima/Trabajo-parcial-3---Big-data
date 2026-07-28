# Arquitectura y máquinas de estado — Parte A

## Flujo dentro de la plataforma

```mermaid
flowchart LR
    CFG[Configuración YAML] --> ENG[Motor concurrente asyncio]
    CLK[Reloj virtual acelerado] --> ENG
    CAT[Catálogo productos y regiones] --> AG[Agentes autónomos]
    ENG --> AG
    AG --> EVT[Eventos raw de A]
    BG[Generador GPS / IoT / movimiento / social] --> EVT
    EVT --> SH{source_hint}
    SH --> WEB[Flujo WEB]
    SH --> MOB[Flujo MOBILE]
    SH --> IOT[Flujo IOT]
    SH --> VEH[Flujo VEHICLE]
    SH --> POS[Flujo POS]
    WEB --> B[Producers del integrante B]
    MOB --> B
    IOT --> B
    VEH --> B
    POS --> B
    B --> K[Kafka]
```

## Máquina de estados común

```mermaid
stateDiagram-v2
    [*] --> OFFLINE
    OFFLINE --> HOME: LOGIN
    HOME --> HOME: PAGE_VIEW
    HOME --> PRODUCT: SEARCH
    HOME --> OFFLINE: EXIT
    PRODUCT --> PRODUCT: VIEW_PRODUCT + SEARCH
    PRODUCT --> CART: VIEW_PRODUCT + ADD_TO_CART
    PRODUCT --> HOME: VIEW_PRODUCT + PAGE_VIEW
    PRODUCT --> OFFLINE: VIEW_PRODUCT + EXIT
    CART --> CART: ADD_TO_CART
    CART --> CART: REMOVE_FROM_CART
    CART --> CART: PAYMENT_FAILED
    CART --> PRODUCT: SEARCH
    CART --> OFFLINE: PURCHASE
    CART --> OFFLINE: EXIT / abandono
```

## Diferenciación de perfiles

| Perfil | Modificación principal |
|---|---|
| COMPRADOR_COMPULSIVO | Poco tiempo entre acciones, alta transición a carrito y compra |
| COMPARADOR | Muchas búsquedas y vistas, compra ocasional |
| COMPRADOR_NOCTURNO | Solo se activa en horas virtuales de 21:00 a 05:59 |
| CLIENTE_PREMIUM | Selecciona productos con precio alto y realiza compras de mayor valor |
| CLIENTE_FRECUENTE | Reinicia sesiones pronto y compra repetidamente |
| USUARIO_EXPLORADOR | Navega y busca, pero el peso de compra y carrito es cero |
| CLIENTE_INDECISO | Alta repetición de agregar y retirar del carrito |
| CLIENTE_ESTACIONAL | Baja intensidad en BASE y alta actividad en eventos empresariales |
