/**
 * Modelo de datos de la Plataforma Inteligente de Audiencias Digitales.
 * Estos tipos reflejan el contrato de mensajes emitido por Apache Flink
 * y reenviado por el backend consumidor vía WebSocket o SSE.
 */

export const EVENT_TYPES = [
  "LOGIN",
  "SEARCH",
  "PAGE_VIEW",
  "VIEW_PRODUCT",
  "ADD_TO_CART",
  "REMOVE_FROM_CART",
  "PURCHASE",
  "PAYMENT_FAILED",
  "GPS_UPDATE",
  "IOT_READING",
  "MOTION_DETECTED",
  "SOCIAL_POST",
] as const;
export type EventType = (typeof EVENT_TYPES)[number];

export type EventCategory = "DIGITAL" | "COMPRAS" | "IOT" | "SISTEMA";

export const AGENT_PROFILES = [
  "COMPRADOR_COMPULSIVO",
  "COMPARADOR",
  "COMPRADOR_NOCTURNO",
  "CLIENTE_PREMIUM",
  "CLIENTE_FRECUENTE",
  "USUARIO_EXPLORADOR",
  "CLIENTE_INDECISO",
  "CLIENTE_ESTACIONAL",
] as const;
export type AgentProfile = (typeof AGENT_PROFILES)[number];

export const SOURCES = ["WEB", "MOBILE", "IOT", "VEHICLE", "POS"] as const;
export type EventSource = (typeof SOURCES)[number];

export const SCENARIOS = [
  "BASE",
  "NAVIDAD",
  "CYBER_MONDAY",
  "BLACK_FRIDAY",
  "FIESTAS_PATRIAS",
  "CAMPANA_ESCOLAR",
  "DIA_DEL_PADRE",
] as const;
export type Scenario = (typeof SCENARIOS)[number];

export type AlertLevel = "INFO" | "WARNING" | "CRITICAL";
export type AlertStatus = "ACTIVA" | "RECONOCIDA" | "RESUELTA";
export type ComponentStatus = "OPERATIVO" | "DEGRADADO" | "DESCONECTADO";
export type ConnectionStatus = "CONECTADO" | "RECONECTANDO" | "DESCONECTADO" | "DEMO";
export type DataMode = "mock" | "websocket" | "sse";
export type TimeRange = "5m" | "15m" | "1h" | "all";

/** Sobre común de todos los eventos JSON publicados en Kafka. */
export interface EventEnvelope<T = Record<string, unknown>> {
  event_id: string;
  schema_version: string;
  event_type: EventType;
  event_timestamp: string;
  ingestion_timestamp: string;
  user_id: string;
  session_id: string;
  agent_profile: AgentProfile;
  source: EventSource;
  city: string;
  region: string;
  scenario: Scenario;
  payload: T;
}

export interface KpiMetrics {
  active_users: number;
  events_per_second: number;
  purchase_conversion: number;
  total_purchases: number;
  total_revenue: number;
  active_alerts: number;
  average_latency_ms: number;
}

export interface DeltaMetrics {
  active_users: number;
  events_per_second: number;
  purchase_conversion: number;
  total_purchases: number;
  total_revenue: number;
  active_alerts: number;
}

export interface EventTypeMetric {
  event_type: EventType;
  category: EventCategory;
  count: number;
  percentage: number;
}

export interface EventTypeIntervalCell {
  bucket: string;
  value: number;
}

export interface EventTypeIntervalRow {
  event_type: EventType;
  cells: EventTypeIntervalCell[];
}

export interface EventTypeIntervalMatrix {
  buckets: string[];
  rows: EventTypeIntervalRow[];
}

export interface AudienceMetric {
  id: string;
  name: string;
  label: string;
  users: number;
  percentage: number;
  change: number;
  priority: "ALTA" | "MEDIA" | "BAJA";
  description: string;
  rules: string[];
  top_events: EventType[];
  top_products: string[];
  top_regions: string[];
  history: SeriesPoint[];
}

export interface ProductMetric {
  id: string;
  name: string;
  category: string;
  views: number;
  avg_dwell_seconds: number;
  units: number;
  orders: number;
  revenue: number;
  change: number;
}

export interface RegionMetric {
  region: string;
  purchases: number;
  revenue: number;
  national_share: number;
  avg_ticket: number;
  conversion: number;
  active_users: number;
}

export interface FunnelStage {
  stage: string;
  key: string;
  value: number;
  drop_from_previous: number;
}

export interface ConversionMetrics {
  overall: number;
  view_to_cart: number;
  cart_to_purchase: number;
  previous_overall: number;
  funnel: FunnelStage[];
  history: SeriesPoint[];
}

export interface Alert {
  id: string;
  level: AlertLevel;
  title: string;
  description: string;
  timestamp: string;
  component: string;
  scenario: Scenario;
  status: AlertStatus;
}

export interface InfrastructureStatus {
  id: string;
  name: string;
  status: ComponentStatus;
  latency_ms: number;
  last_heartbeat: string;
  messages_processed: number;
  errors: number;
  responsibility: string;
  inputs: string[];
  outputs: string[];
}

export interface SeriesPoint {
  t: string;
  value: number;
}

export interface ThroughputPoint {
  timestamp: number;
  label: string;
  eps: number;
  purchases: number;
}

export interface ProfileMetric {
  profile: AgentProfile;
  users: number;
  purchases: number;
  conversion: number;
  revenue: number;
}

export interface SourceMetric {
  source: EventSource;
  events: number;
  share: number;
}

/** Snapshot consolidado que el dashboard consume (topic dashboard-metrics). */
export interface DashboardMetrics {
  timestamp: string;
  scenario: Scenario;
  metrics: KpiMetrics;
  deltas: DeltaMetrics;
  sparklines: Record<keyof DeltaMetrics, number[]>;
  events_by_type: EventTypeMetric[];
  event_type_intervals: EventTypeIntervalMatrix;
  audiences: AudienceMetric[];
  top_viewed_products: ProductMetric[];
  top_purchased_products: ProductMetric[];
  regions: RegionMetric[];
  conversion: ConversionMetrics;
  alerts: Alert[];
  infrastructure: InfrastructureStatus[];
  profiles: ProfileMetric[];
  sources: SourceMetric[];
}

export interface ScenarioResult {
  scenario: Scenario;
  total_events: number;
  avg_eps: number;
  peak_eps: number;
  max_active_users: number;
  purchases: number;
  conversion: number;
  total_revenue: number;
  abandoned_carts: number;
  failed_payments: number;
  avg_latency_ms: number;
  alerts: number;
  critical_alerts: number;
}

export type RealtimeMessageType =
  | "dashboard_update"
  | "alert_created"
  | "infrastructure_update"
  | "scenario_changed"
  | "heartbeat"
  | "error";

export interface RealtimeMessage {
  message_type: RealtimeMessageType;
  timestamp: string;
  scenario: Scenario;
  metrics?: KpiMetrics;
  snapshot?: DashboardMetrics;
  alert?: Alert;
  infrastructure?: InfrastructureStatus[];
  error?: string;
}

export interface GlobalFilters {
  scenario: Scenario;
  timeRange: TimeRange;
  region: string;
  profile: AgentProfile | "TODOS";
  eventType: EventType | "TODOS";
  source: EventSource | "TODOS";
  alertLevel: AlertLevel | "TODOS";
  /** Selección cruzada: audiencia activa (id) o "TODAS". */
  audience: string;
  /** Selección cruzada: producto activo (id) o "TODOS". */
  product: string;
  /** Selección cruzada: etapa del embudo (key) o "TODAS". */
  funnelStage: string;
  /** Selección cruzada: intervalo temporal explícito seleccionado en un gráfico. */
  window: { from: string; to: string } | null;
}
