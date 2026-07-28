# Sección del informe — Implementación del simulador de agentes

## Diseño de la solución

La parte A implementa el componente encargado de producir el comportamiento sintético de los usuarios antes de la publicación en Kafka. El simulador se desarrolló en Python y utiliza concurrencia asíncrona, de manera que cada usuario virtual se ejecuta como una tarea independiente y puede generar eventos al mismo tiempo que los demás. Esta decisión permite aumentar o reducir la cantidad de usuarios mediante configuración, sin crear manualmente un hilo del sistema operativo por cada agente y sin modificar la lógica de los perfiles.

El funcionamiento se apoya en un reloj virtual acelerado, el cual transforma el tiempo real de ejecución en tiempo simulado. Con una velocidad de 3600, cada segundo real representa una hora virtual. Esto permite recorrer rápidamente periodos completos y comprobar comportamientos dependientes de la hora, principalmente el comprador nocturno. El campo `event_timestamp` se obtiene siempre de este reloj y no de la hora real de publicación, porque el contrato diferencia el momento de ocurrencia del evento y el momento de ingesta que posteriormente agrega el productor.

## Máquinas de estado

Cada usuario se modeló mediante los estados `OFFLINE`, `HOME`, `PRODUCT` y `CART`. Al comenzar una sesión se emite `LOGIN` y el agente pasa a `HOME`; desde este estado puede visualizar una página, buscar un producto o salir. Después de una búsqueda pasa a `PRODUCT`, donde emite `VIEW_PRODUCT` y decide si continúa buscando, agrega el producto al carrito, vuelve a una página general o abandona la sesión. En `CART` puede agregar otro producto, retirar productos, realizar la compra, sufrir un pago rechazado, buscar nuevamente o abandonar el carrito.

Los ocho perfiles comparten la misma estructura general, pero no las mismas probabilidades de transición. El comprador compulsivo presenta mayor peso hacia `ADD_TO_CART` y `PURCHASE`, el comparador repite `SEARCH`, el nocturno restringe sus horas activas, el premium utiliza un rango de precios alto, el frecuente tiene pausas cortas entre sesiones, el explorador tiene probabilidad cero de compra, el indeciso presenta mayor peso para `REMOVE_FROM_CART`, y el estacional recibe multiplicadores fuertes cuando el escenario deja de ser `BASE`.

## Generación de eventos y manejo del estado

El simulador genera los doce tipos definidos en el contrato: `LOGIN`, `SEARCH`, `PAGE_VIEW`, `VIEW_PRODUCT`, `ADD_TO_CART`, `REMOVE_FROM_CART`, `PURCHASE`, `PAYMENT_FAILED`, `GPS_UPDATE`, `IOT_READING`, `MOTION_DETECTED` y `SOCIAL_POST`. Los primeros ocho provienen principalmente de las acciones de navegación y compra, mientras que los cuatro restantes se generan en una tarea de eventos de contexto que utiliza usuarios existentes para mantener identificadores, perfil y ubicación válidos.

El carrito se mantiene dentro del agente durante la sesión. El mismo `cart_id` aparece al agregar, retirar, comprar o fallar un pago. La compra contiene un arreglo completo de ítems, incluyendo nombre, categoría, precio unitario, cantidad y subtotal. Esta representación evita que el procesador tenga que reconstruir el monto a partir de todos los eventos anteriores y facilita el cálculo posterior de ingresos y productos comprados.

## Escenarios empresariales

Los escenarios se definieron en archivos YAML separados. `BASE` mantiene los pesos normales, `NAVIDAD` incrementa juguetes y tecnología, `CYBER_MONDAY` concentra actividad digital y descuentos tecnológicos, `BLACK_FRIDAY` representa la mayor carga y probabilidad de compra, `FIESTAS_PATRIAS` incrementa hogar, moda y deportes, `CAMPANA_ESCOLAR` prioriza productos escolares, y `DIA_DEL_PADRE` incrementa tecnología, deportes y moda. Cada archivo puede modificar actividad, compras, agregado al carrito, fallas de pago, descuentos, categorías preferidas y actividad de perfiles específicos.

## Frontera con productores Kafka

La parte A entrega los campos `event_type`, `event_timestamp`, `user_id`, `session_id`, `agent_profile`, `city`, `region`, `scenario` y `payload`. Además, genera internamente un `source_hint` para indicar si el evento debe pasar por el productor web, mobile, IoT, vehicle o POS. La parte B agrega `event_id`, `schema_version`, `ingestion_timestamp` y `source`, conserva el tiempo virtual y usa `user_id` como clave de partición.

Durante la revisión se encontró que el contrato menciona cambios de escenario y señales de control dentro de `system-events`, pero no define su tipo ni payload entre los doce eventos. Por esta razón no se creó un evento adicional sin acuerdo del grupo. Una futura incorporación debe registrarse como una nueva versión del contrato.

## Pruebas y evidencia

La implementación incluye validación de campos obligatorios para cada payload, una herramienta que revisa todos los registros JSONL y pruebas automáticas que comprueban la existencia de los ocho perfiles y los doce tipos de evento. En cada corrida se produce un archivo consolidado, archivos separados por fuente y un resumen con cantidad total, distribución por tipo de evento, perfil y fuente. Estos archivos permiten demostrar la generación de carga, comparar escenarios y entregar una interfaz reproducible al componente de ingesta.
