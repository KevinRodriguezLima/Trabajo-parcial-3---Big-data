import type {
  AgentProfile,
  EventCategory,
  EventType,
  Scenario,
} from "@/types";

/** Catálogos estáticos del dominio simulado. */

export interface ScenarioConfig {
  id: Scenario;
  label: string;
  description: string;
  enabled: boolean;
  epsMin: number;
  epsMax: number;
  conversion: number;
  ticket: number;
  latency: number;
  alertRate: number;
  failedPaymentRate: number;
  color: string;
}

export const SCENARIO_CONFIG: Record<Scenario, ScenarioConfig> = {
  BASE: {
    id: "BASE",
    label: "Base",
    description: "Actividad normal del sistema.",
    enabled: true,
    epsMin: 80,
    epsMax: 130,
    conversion: 0.098,
    ticket: 318,
    latency: 92,
    alertRate: 0.04,
    failedPaymentRate: 0.022,
    color: "var(--color-info)",
  },
  NAVIDAD: {
    id: "NAVIDAD",
    label: "Navidad",
    description: "Incremento de compras, mayor interés en regalos y aumento de tráfico.",
    enabled: true,
    epsMin: 120,
    epsMax: 220,
    conversion: 0.115,
    ticket: 392,
    latency: 118,
    alertRate: 0.09,
    failedPaymentRate: 0.031,
    color: "var(--color-success)",
  },
  CYBER_MONDAY: {
    id: "CYBER_MONDAY",
    label: "Cyber Monday",
    description: "Pico elevado de búsquedas, visualizaciones y conversiones.",
    enabled: true,
    epsMin: 200,
    epsMax: 400,
    conversion: 0.128,
    ticket: 421,
    latency: 156,
    alertRate: 0.16,
    failedPaymentRate: 0.045,
    color: "var(--color-special)",
  },
  BLACK_FRIDAY: {
    id: "BLACK_FRIDAY",
    label: "Black Friday",
    description: "Máxima concurrencia, altos eventos por segundo y mayor cantidad de alertas.",
    enabled: true,
    epsMin: 300,
    epsMax: 600,
    conversion: 0.121,
    ticket: 447,
    latency: 214,
    alertRate: 0.27,
    failedPaymentRate: 0.068,
    color: "var(--color-critical)",
  },
  FIESTAS_PATRIAS: {
    id: "FIESTAS_PATRIAS",
    label: "Fiestas Patrias",
    description: "Campaña nacional con incremento moderado de tráfico regional.",
    enabled: false,
    epsMin: 110,
    epsMax: 190,
    conversion: 0.106,
    ticket: 355,
    latency: 108,
    alertRate: 0.07,
    failedPaymentRate: 0.028,
    color: "var(--color-warning)",
  },
  CAMPANA_ESCOLAR: {
    id: "CAMPANA_ESCOLAR",
    label: "Campaña Escolar",
    description: "Demanda concentrada en útiles, tecnología educativa y mobiliario.",
    enabled: false,
    epsMin: 100,
    epsMax: 170,
    conversion: 0.102,
    ticket: 289,
    latency: 101,
    alertRate: 0.06,
    failedPaymentRate: 0.026,
    color: "var(--color-info)",
  },
  DIA_DEL_PADRE: {
    id: "DIA_DEL_PADRE",
    label: "Día del Padre",
    description: "Pico corto de compras de regalos con alta conversión móvil.",
    enabled: false,
    epsMin: 115,
    epsMax: 200,
    conversion: 0.112,
    ticket: 372,
    latency: 112,
    alertRate: 0.08,
    failedPaymentRate: 0.029,
    color: "var(--color-success)",
  },
};

export const PRIMARY_SCENARIOS: Scenario[] = [
  "BASE",
  "NAVIDAD",
  "CYBER_MONDAY",
  "BLACK_FRIDAY",
];

export const EVENT_CATEGORY: Record<EventType, EventCategory> = {
  LOGIN: "DIGITAL",
  SEARCH: "DIGITAL",
  PAGE_VIEW: "DIGITAL",
  VIEW_PRODUCT: "DIGITAL",
  ADD_TO_CART: "COMPRAS",
  REMOVE_FROM_CART: "COMPRAS",
  PURCHASE: "COMPRAS",
  PAYMENT_FAILED: "SISTEMA",
  GPS_UPDATE: "IOT",
  IOT_READING: "IOT",
  MOTION_DETECTED: "IOT",
  SOCIAL_POST: "DIGITAL",
};

/** Peso relativo de cada tipo de evento sobre el total de tráfico. */
export const EVENT_WEIGHTS: Record<EventType, number> = {
  PAGE_VIEW: 0.215,
  VIEW_PRODUCT: 0.185,
  SEARCH: 0.135,
  GPS_UPDATE: 0.098,
  IOT_READING: 0.085,
  LOGIN: 0.072,
  ADD_TO_CART: 0.066,
  SOCIAL_POST: 0.045,
  MOTION_DETECTED: 0.038,
  REMOVE_FROM_CART: 0.027,
  PURCHASE: 0.024,
  PAYMENT_FAILED: 0.01,
};

export interface ProductSeed {
  id: string;
  name: string;
  category: string;
  price: number;
  popularity: number;
  giftAffinity: number;
}

export const PRODUCTS: ProductSeed[] = [
  { id: "P-001", name: "Laptop Lenovo IdeaPad 3", category: "Cómputo", price: 2199, popularity: 1, giftAffinity: 0.6 },
  { id: "P-002", name: "Smartphone Samsung Galaxy A55", category: "Telefonía", price: 1699, popularity: 0.94, giftAffinity: 0.9 },
  { id: "P-003", name: "Audífonos Bluetooth JBL Tune", category: "Audio", price: 249, popularity: 0.88, giftAffinity: 0.95 },
  { id: "P-004", name: 'Smart TV 55" LG UHD', category: "Televisores", price: 1899, popularity: 0.81, giftAffinity: 0.7 },
  { id: "P-005", name: "Mouse inalámbrico Logitech M170", category: "Accesorios", price: 69, popularity: 0.76, giftAffinity: 0.4 },
  { id: "P-006", name: "Tablet Xiaomi Redmi Pad SE", category: "Cómputo", price: 899, popularity: 0.71, giftAffinity: 0.8 },
  { id: "P-007", name: "Teclado mecánico Redragon K552", category: "Accesorios", price: 189, popularity: 0.66, giftAffinity: 0.55 },
  { id: "P-008", name: 'Monitor gaming AOC 24" 165Hz', category: "Monitores", price: 749, popularity: 0.62, giftAffinity: 0.45 },
  { id: "P-009", name: "Consola PlayStation 5 Slim", category: "Gaming", price: 2599, popularity: 0.58, giftAffinity: 0.98 },
  { id: "P-010", name: "Smartwatch Amazfit GTS 4", category: "Wearables", price: 549, popularity: 0.54, giftAffinity: 0.85 },
  { id: "P-011", name: "Impresora Epson EcoTank L3250", category: "Oficina", price: 799, popularity: 0.5, giftAffinity: 0.25 },
  { id: "P-012", name: "Cafetera Oster de goteo", category: "Hogar", price: 229, popularity: 0.47, giftAffinity: 0.6 },
  { id: "P-013", name: "Aspiradora robot Xiaomi S10", category: "Hogar", price: 1099, popularity: 0.43, giftAffinity: 0.65 },
  { id: "P-014", name: "Silla ergonómica Klip Xtreme", category: "Oficina", price: 649, popularity: 0.4, giftAffinity: 0.3 },
  { id: "P-015", name: "Parlante Bluetooth Sony SRS-XB13", category: "Audio", price: 199, popularity: 0.37, giftAffinity: 0.88 },
  { id: "P-016", name: "Disco SSD Kingston 1TB NVMe", category: "Almacenamiento", price: 329, popularity: 0.34, giftAffinity: 0.2 },
  { id: "P-017", name: "Cámara de seguridad TP-Link Tapo", category: "IoT", price: 149, popularity: 0.31, giftAffinity: 0.35 },
  { id: "P-018", name: "Freidora de aire Imaco 5L", category: "Hogar", price: 379, popularity: 0.28, giftAffinity: 0.72 },
  { id: "P-019", name: "Mochila antirrobo Xtrem", category: "Accesorios", price: 159, popularity: 0.25, giftAffinity: 0.5 },
  { id: "P-020", name: "Router WiFi 6 TP-Link AX1500", category: "Redes", price: 269, popularity: 0.22, giftAffinity: 0.15 },
];

export interface RegionSeed {
  region: string;
  weight: number;
}

export const REGIONS: RegionSeed[] = [
  { region: "Lima", weight: 0.34 },
  { region: "Arequipa", weight: 0.17 },
  { region: "La Libertad", weight: 0.09 },
  { region: "Cusco", weight: 0.083 },
  { region: "Piura", weight: 0.072 },
  { region: "Junín", weight: 0.062 },
  { region: "Puno", weight: 0.055 },
  { region: "Ica", weight: 0.049 },
  { region: "Tacna", weight: 0.043 },
  { region: "Moquegua", weight: 0.036 },
];

export interface AudienceSeed {
  id: string;
  name: string;
  label: string;
  weight: number;
  priority: "ALTA" | "MEDIA" | "BAJA";
  description: string;
  rules: string[];
  top_events: EventType[];
}

export const AUDIENCES: AudienceSeed[] = [
  {
    id: "comprador-compulsivo",
    name: "COMPRADOR_COMPULSIVO",
    label: "Comprador compulsivo",
    weight: 0.16,
    priority: "ALTA",
    description: "Usuarios con alta recurrencia de compras dentro de una ventana reciente.",
    rules: [
      "≥ 3 eventos PURCHASE en ventana de 10 minutos",
      "Eventos agrupados por user_id",
    ],
    top_events: ["PURCHASE", "ADD_TO_CART", "VIEW_PRODUCT"],
  },
  {
    id: "comparador-activo",
    name: "COMPARADOR_ACTIVO",
    label: "Comparador activo",
    weight: 0.17,
    priority: "MEDIA",
    description: "Usuarios que revisan varios productos distintos antes de decidir.",
    rules: [
      "≥ 5 eventos VIEW_PRODUCT en ventana de 5 minutos",
      "Sin ADD_TO_CART en la misma ventana",
    ],
    top_events: ["VIEW_PRODUCT", "SEARCH", "PAGE_VIEW"],
  },
  {
    id: "abandono-carrito",
    name: "CARRITO_ABANDONADO",
    label: "Abandono de carrito",
    weight: 0.134,
    priority: "ALTA",
    description: "Sesiones con carrito conformado sin evento de compra en la ventana de cierre.",
    rules: ["ADD_TO_CART sin PURCHASE tras 15 minutos", "Sin REMOVE_FROM_CART explícito"],
    top_events: ["ADD_TO_CART", "PAGE_VIEW", "REMOVE_FROM_CART"],
  },
  {
    id: "comprador-nocturno",
    name: "COMPRADOR_NOCTURNO",
    label: "Comprador nocturno",
    weight: 0.12,
    priority: "MEDIA",
    description: "Actividad concentrada en horario nocturno.",
    rules: ["≥ 3 eventos entre 22:00 y 06:00", "Evaluado sobre event_timestamp"],
    top_events: ["VIEW_PRODUCT", "PURCHASE", "SOCIAL_POST"],
  },
  {
    id: "usuario-alto-valor",
    name: "USUARIO_ALTO_VALOR",
    label: "Usuario alto valor",
    weight: 0.11,
    priority: "ALTA",
    description: "Compradores con acumulado de compra alto en la ejecución.",
    rules: ["Compras acumuladas ≥ S/ 1,000", "Monto calculado desde eventos PURCHASE"],
    top_events: ["PURCHASE", "VIEW_PRODUCT", "ADD_TO_CART"],
  },
  {
    id: "navegador-indeciso",
    name: "NAVEGADOR_INDECISO",
    label: "Navegador indeciso",
    weight: 0.10,
    priority: "MEDIA",
    description: "Usuarios que alternan adiciones y retiros del carrito sin concretar rápidamente.",
    rules: ["≥ 3 ciclos ADD_TO_CART / REMOVE_FROM_CART", "Ventana de 30 minutos"],
    top_events: ["ADD_TO_CART", "REMOVE_FROM_CART", "VIEW_PRODUCT"],
  },
  {
    id: "usuario-multi-dispositivo",
    name: "USUARIO_MULTI_DISPOSITIVO",
    label: "Usuario multidispositivo",
    weight: 0.09,
    priority: "BAJA",
    description: "Usuarios que interactúan desde dos o más fuentes durante la misma ejecución.",
    rules: ["Eventos desde ≥ 2 fuentes distintas", "Fuentes WEB, MOBILE, IOT, VEHICLE o POS"],
    top_events: ["LOGIN", "PAGE_VIEW", "GPS_UPDATE"],
  },
];

export const PROFILE_WEIGHTS: Record<AgentProfile, number> = {
  COMPRADOR_COMPULSIVO: 0.11,
  COMPARADOR: 0.16,
  COMPRADOR_NOCTURNO: 0.09,
  CLIENTE_PREMIUM: 0.08,
  CLIENTE_FRECUENTE: 0.15,
  USUARIO_EXPLORADOR: 0.19,
  CLIENTE_INDECISO: 0.13,
  CLIENTE_ESTACIONAL: 0.09,
};

export const ALERT_TEMPLATES: Array<{
  level: "INFO" | "WARNING" | "CRITICAL";
  title: string;
  description: string;
  component: string;
}> = [
  {
    level: "WARNING",
    title: "Pico inusual de eventos por segundo",
    description: "El throughput superó en 2.4σ la media móvil de los últimos 5 minutos.",
    component: "Apache Flink",
  },
  {
    level: "WARNING",
    title: "Alta tasa de pagos rechazados",
    description: "Los eventos PAYMENT_FAILED representan más del 6 % de los intentos de compra.",
    component: "Pasarela de pagos",
  },
  {
    level: "WARNING",
    title: "Incremento de abandono de carrito",
    description: "La audiencia ABANDONO_CARRITO creció por encima del umbral configurado.",
    component: "Job de audiencias",
  },
  {
    level: "WARNING",
    title: "Caída repentina de conversión",
    description: "La conversión cayó más de 3 puntos porcentuales respecto a la ventana anterior.",
    component: "Job de conversión",
  },
  {
    level: "WARNING",
    title: "Latencia alta de procesamiento",
    description: "La latencia extremo a extremo supera los 250 ms sostenidos.",
    component: "Apache Flink",
  },
  {
    level: "WARNING",
    title: "Pérdida de conexión con Kafka",
    description: "El consumidor perdió el heartbeat con el broker principal del clúster.",
    component: "Apache Kafka",
  },
  {
    level: "WARNING",
    title: "Pérdida de conexión con Flink",
    description: "El JobManager dejó de reportar checkpoints durante 30 segundos.",
    component: "Apache Flink",
  },
  {
    level: "WARNING",
    title: "Eventos enviados al dead-letter topic",
    description: "Se detectaron eventos con esquema inválido derivados a dead-letter.",
    component: "Topic dead-letter",
  },
  {
    level: "INFO",
    title: "Actividad anómala por región",
    description: "Una región concentra un volumen atípico de compras respecto a su histórico.",
    component: "Job de regiones",
  },
  {
    level: "INFO",
    title: "Sensor IoT fuera de rango",
    description: "Una lectura IOT_READING reportó valores fuera del rango operativo esperado.",
    component: "Simuladores IoT",
  },
];
