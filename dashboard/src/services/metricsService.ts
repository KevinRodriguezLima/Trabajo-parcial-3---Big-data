/**
 * metricsService
 * ---------------------------------------------------------------------------
 * Motor de consolidación de métricas. En producción estos valores llegan ya
 * calculados desde Apache Flink (topics dashboard-metrics / dashboard-audiences
 * / dashboard-alerts). Aquí se replica ese contrato para el modo demostración,
 * manteniendo coherencia entre indicadores (no son números aleatorios sueltos).
 */
import {
  ALERT_TEMPLATES,
  AUDIENCES,
  EVENT_CATEGORY,
  EVENT_WEIGHTS,
  PRODUCTS,
  PROFILE_WEIGHTS,
  REGIONS,
  SCENARIO_CONFIG,
} from "@/data/catalog";
import {
  AGENT_PROFILES,
  EVENT_TYPES,
  SOURCES,
  type Alert,
  type AudienceMetric,
  type DashboardMetrics,
  type EventTypeMetric,
  type InfrastructureStatus,
  type ProductMetric,
  type ProfileMetric,
  type RegionMetric,
  type Scenario,
  type ScenarioResult,
  type SeriesPoint,
  type SourceMetric,
} from "@/types";

/** Generador pseudoaleatorio determinista (mulberry32). */
export function createRng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a += 0x6d2b79f5;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hashString(value: string): number {
  let h = 2166136261;
  for (let i = 0; i < value.length; i++) {
    h ^= value.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

const SOURCE_SHARES: Record<(typeof SOURCES)[number], number> = {
  WEB: 0.42,
  MOBILE: 0.33,
  IOT: 0.13,
  VEHICLE: 0.06,
  POS: 0.06,
};

const INFRA_SEED = [
  {
    id: "simuladores",
    name: "Simuladores de agentes",
    responsibility: "Generan el comportamiento sintético de usuarios digitales y sensores.",
    inputs: ["Perfiles de agente", "Configuración de escenario"],
    outputs: ["Eventos JSON con sobre común"],
  },
  {
    id: "productores",
    name: "Productores Kafka",
    responsibility: "Serializan y publican los eventos en los topics de entrada.",
    inputs: ["Eventos de simuladores"],
    outputs: ["user-events", "purchase-events", "iot-events", "system-events"],
  },
  {
    id: "kafka",
    name: "Apache Kafka",
    responsibility: "Bus de eventos distribuido, particionado y con retención configurable.",
    inputs: ["Topics de entrada"],
    outputs: ["Streams particionados hacia Flink", "dead-letter"],
  },
  {
    id: "flink",
    name: "Apache Flink",
    responsibility: "Procesa ventanas deslizantes, detecta audiencias y consolida métricas.",
    inputs: ["user-events", "purchase-events", "iot-events", "system-events"],
    outputs: ["dashboard-metrics", "dashboard-audiences", "dashboard-alerts"],
  },
  {
    id: "backend",
    name: "Backend consumidor",
    responsibility: "Consume los topics de resultados y mantiene el snapshot en memoria.",
    inputs: ["dashboard-metrics", "dashboard-audiences", "dashboard-alerts"],
    outputs: ["GET /api/dashboard/snapshot", "Mensajes de difusión"],
  },
  {
    id: "transporte",
    name: "WebSocket / SSE",
    responsibility: "Difunde en tiempo real los snapshots hacia los clientes conectados.",
    inputs: ["Snapshot consolidado"],
    outputs: ["/ws/dashboard", "/events/dashboard"],
  },
  {
    id: "dashboard",
    name: "Dashboard web",
    responsibility: "Renderiza los diez indicadores obligatorios y el análisis experimental.",
    inputs: ["dashboard_update", "alert_created", "infrastructure_update"],
    outputs: ["Visualizaciones, exportaciones y evidencias"],
  },
];

function seriesFrom(values: number[], stepSeconds = 60): SeriesPoint[] {
  const now = Date.now();
  return values.map((value, i) => ({
    t: new Date(now - (values.length - 1 - i) * stepSeconds * 1000).toISOString(),
    value,
  }));
}

export interface EngineTick {
  snapshot: DashboardMetrics;
  newAlert?: Alert;
}

/**
 * Motor con estado que emula la salida acumulada de un job de Flink.
 * Mantiene acumuladores para que compras, ingresos y conversión sean coherentes.
 */
export class ScenarioEngine {
  private tick = 0;
  private rng: () => number;
  private totalEvents = 0;
  private totalPurchases = 0;
  private totalRevenue = 0;
  private totalViews = 0;
  private totalCarts = 0;
  private totalCheckouts = 0;
  private failedPayments = 0;
  private alerts: Alert[] = [];
  private conversionHistory: number[] = [];
  private previous: { users: number; eps: number; conversion: number; purchases: number; revenue: number; alerts: number } | null =
    null;
  private sparkStore: Record<string, number[]> = {};

  constructor(
    public scenario: Scenario,
    seed = 20260729,
  ) {
    this.rng = createRng(seed + hashString(scenario));
    this.seedAlerts();
    // Precalentamiento para que el primer snapshot ya tenga volumen realista.
    for (let i = 0; i < 45; i++) this.advance(false);
  }

  reset(scenario: Scenario) {
    Object.assign(this, new ScenarioEngine(scenario));
  }

  private cfg() {
    return SCENARIO_CONFIG[this.scenario];
  }

  private seedAlerts() {
    const cfg = this.cfg();
    const count = Math.round(3 + cfg.alertRate * 20);
    for (let i = 0; i < count; i++) {
      const tpl = ALERT_TEMPLATES[Math.floor(this.rng() * ALERT_TEMPLATES.length)];
      this.alerts.push({
        id: `alt_${this.scenario}_${i}_${Math.floor(this.rng() * 1e6).toString(16)}`,
        level: tpl.level,
        title: tpl.title,
        description: tpl.description,
        component: tpl.component,
        scenario: this.scenario,
        status: this.rng() > 0.72 ? "RECONOCIDA" : "ACTIVA",
        timestamp: new Date(Date.now() - Math.floor(this.rng() * 1800) * 1000).toISOString(),
      });
    }
  }

  private currentEps(): number {
    const cfg = this.cfg();
    const mid = (cfg.epsMin + cfg.epsMax) / 2;
    const amp = (cfg.epsMax - cfg.epsMin) / 2;
    const wave = Math.sin(this.tick / 14) * 0.62 + Math.sin(this.tick / 5.3) * 0.24;
    const noise = (this.rng() - 0.5) * 0.22;
    const value = mid + amp * (wave + noise);
    return Math.max(cfg.epsMin * 0.85, Math.min(cfg.epsMax * 1.02, value));
  }

  private pushSpark(key: string, value: number) {
    const arr = this.sparkStore[key] ?? [];
    arr.push(value);
    if (arr.length > 24) arr.shift();
    this.sparkStore[key] = arr;
  }

  /** Avanza el reloj del motor un segundo simulado. */
  private advance(record = true): Alert | undefined {
    const cfg = this.cfg();
    this.tick += 1;
    const eps = this.currentEps();
    this.totalEvents += eps;

    const views = eps * EVENT_WEIGHTS.VIEW_PRODUCT;
    const carts = eps * EVENT_WEIGHTS.ADD_TO_CART;
    const checkouts = carts * 0.42;
    const purchases = views * cfg.conversion;
    this.totalViews += views;
    this.totalCarts += carts;
    this.totalCheckouts += checkouts;
    this.totalPurchases += purchases;
    this.totalRevenue += purchases * cfg.ticket * (0.9 + this.rng() * 0.2);
    this.failedPayments += purchases * cfg.failedPaymentRate;

    const conversion = this.totalViews > 0 ? this.totalPurchases / this.totalViews : 0;
    this.conversionHistory.push(conversion * 100);
    if (this.conversionHistory.length > 40) this.conversionHistory.shift();

    if (record) {
      this.pushSpark("active_users", Math.round(eps * 6.4));
      this.pushSpark("events_per_second", eps);
      this.pushSpark("purchase_conversion", conversion * 100);
      this.pushSpark("total_purchases", this.totalPurchases);
      this.pushSpark("total_revenue", this.totalRevenue);
      this.pushSpark("active_alerts", this.alerts.filter((a) => a.status === "ACTIVA").length);
    }

    let created: Alert | undefined;
    if (record && this.rng() < cfg.alertRate * 0.28) {
      const tpl = ALERT_TEMPLATES[Math.floor(this.rng() * ALERT_TEMPLATES.length)];
      created = {
        id: `alt_${Date.now()}_${Math.floor(this.rng() * 1e6).toString(16)}`,
        level: tpl.level,
        title: tpl.title,
        description: tpl.description,
        component: tpl.component,
        scenario: this.scenario,
        status: "ACTIVA",
        timestamp: new Date().toISOString(),
      };
      this.alerts = [created, ...this.alerts].slice(0, 60);
    }
    return created;
  }

  acknowledge(id: string) {
    this.alerts = this.alerts.map((a) => (a.id === id ? { ...a, status: "RECONOCIDA" } : a));
  }

  resolve(id: string) {
    this.alerts = this.alerts.map((a) => (a.id === id ? { ...a, status: "RESUELTA" } : a));
  }

  next(): EngineTick {
    const newAlert = this.advance();
    return { snapshot: this.buildSnapshot(), newAlert };
  }

  buildSnapshot(): DashboardMetrics {
    const cfg = this.cfg();
    const eps = this.sparkStore.events_per_second?.at(-1) ?? this.currentEps();
    const activeUsers = Math.round(eps * 6.4);
    const conversion = this.totalViews > 0 ? this.totalPurchases / this.totalViews : 0;
    const purchases = Math.round(this.totalPurchases);
    const revenue = this.totalRevenue;
    const activeAlerts = this.alerts.filter((a) => a.status === "ACTIVA").length;
    const latency = Math.round(cfg.latency * (0.88 + this.rng() * 0.28));

    const prev = this.previous ?? {
      users: activeUsers * 0.95,
      eps: eps * 0.96,
      conversion: conversion * 0.97,
      purchases: purchases * 0.94,
      revenue: revenue * 0.93,
      alerts: Math.max(1, activeAlerts - 1),
    };
    const pct = (curr: number, before: number) => (before === 0 ? 0 : ((curr - before) / before) * 100);
    const deltas = {
      active_users: pct(activeUsers, prev.users),
      events_per_second: pct(eps, prev.eps),
      purchase_conversion: pct(conversion, prev.conversion),
      total_purchases: pct(purchases, prev.purchases),
      total_revenue: pct(revenue, prev.revenue),
      active_alerts: pct(activeAlerts, prev.alerts),
    };
    this.previous = {
      users: activeUsers,
      eps,
      conversion,
      purchases,
      revenue,
      alerts: activeAlerts,
    };

    return {
      timestamp: new Date().toISOString(),
      scenario: this.scenario,
      metrics: {
        active_users: activeUsers,
        events_per_second: Number(eps.toFixed(1)),
        purchase_conversion: conversion,
        total_purchases: purchases,
        total_revenue: revenue,
        active_alerts: activeAlerts,
        average_latency_ms: latency,
      },
      deltas,
      sparklines: {
        active_users: this.sparkStore.active_users ?? [],
        events_per_second: this.sparkStore.events_per_second ?? [],
        purchase_conversion: this.sparkStore.purchase_conversion ?? [],
        total_purchases: this.sparkStore.total_purchases ?? [],
        total_revenue: this.sparkStore.total_revenue ?? [],
        active_alerts: this.sparkStore.active_alerts ?? [],
      },
      events_by_type: this.buildEventsByType(),
      event_type_intervals: { buckets: [], rows: [] },
      audiences: this.buildAudiences(activeUsers),
      top_viewed_products: this.buildProducts("views"),
      top_purchased_products: this.buildProducts("purchases"),
      regions: this.buildRegions(purchases, revenue, activeUsers),
      conversion: {
        overall: conversion,
        view_to_cart: this.totalViews > 0 ? this.totalCarts / this.totalViews : 0,
        cart_to_purchase: this.totalCarts > 0 ? this.totalPurchases / this.totalCarts : 0,
        previous_overall: conversion * (0.93 + this.rng() * 0.06),
        funnel: this.buildFunnel(),
        history: seriesFrom(this.conversionHistory.map((v) => Number(v.toFixed(2)))),
      },
      alerts: [...this.alerts],
      infrastructure: this.buildInfrastructure(latency),
      profiles: this.buildProfiles(activeUsers, purchases, revenue),
      sources: this.buildSources(),
    };
  }

  private buildEventsByType(): EventTypeMetric[] {
    const total = this.totalEvents;
    return EVENT_TYPES.map((type) => {
      const count = Math.round(total * EVENT_WEIGHTS[type]);
      return {
        event_type: type,
        category: EVENT_CATEGORY[type],
        count,
        percentage: Number((EVENT_WEIGHTS[type] * 100).toFixed(2)),
      };
    }).sort((a, b) => b.count - a.count);
  }

  private buildAudiences(activeUsers: number): AudienceMetric[] {
    return AUDIENCES.map((seed, index) => {
      const bump = this.scenario === "BASE" ? 1 : 1.08;
      const users = Math.round(activeUsers * seed.weight * bump);
      const rng = createRng(hashString(seed.id + this.scenario));
      const history = Array.from({ length: 12 }, (_, i) =>
        Math.round(users * (0.7 + rng() * 0.45) * (0.85 + i * 0.015)),
      );
      return {
        id: seed.id,
        name: seed.name,
        label: seed.label,
        users,
        percentage: Number(((users / Math.max(1, activeUsers)) * 100).toFixed(2)),
        change: Number(((rng() - 0.4) * 18).toFixed(1)),
        priority: seed.priority,
        description: seed.description,
        rules: seed.rules,
        top_events: seed.top_events,
        top_products: PRODUCTS.slice(index % 5, (index % 5) + 3).map((p) => p.name),
        top_regions: REGIONS.slice(index % 4, (index % 4) + 3).map((r) => r.region),
        history: seriesFrom(history),
      };
    }).sort((a, b) => b.users - a.users);
  }

  private buildProducts(kind: "views" | "purchases"): ProductMetric[] {
    const cfg = this.cfg();
    const giftBoost = this.scenario === "NAVIDAD" || this.scenario === "DIA_DEL_PADRE";
    return PRODUCTS.map((p) => {
      const rng = createRng(hashString(p.id + this.scenario + kind));
      const affinity = giftBoost ? 0.55 + p.giftAffinity * 0.75 : 1;
      const weight = p.popularity * affinity * (0.85 + rng() * 0.3);
      const views = Math.round(this.totalViews * weight * 0.055);
      const units = Math.round(views * cfg.conversion * (0.9 + rng() * 0.35));
      const orders = Math.max(1, Math.round(units * 0.82));
      return {
        id: p.id,
        name: p.name,
        category: p.category,
        views,
        avg_dwell_seconds: Number((28 + rng() * 95).toFixed(1)),
        units,
        orders,
        revenue: units * p.price,
        change: Number(((rng() - 0.42) * 26).toFixed(1)),
      };
    }).sort((a, b) => (kind === "views" ? b.views - a.views : b.units - a.units));
  }

  private buildRegions(purchases: number, revenue: number, activeUsers: number): RegionMetric[] {
    const cfg = this.cfg();
    return REGIONS.map((r) => {
      const rng = createRng(hashString(r.region + this.scenario));
      const w = r.weight * (0.92 + rng() * 0.16);
      const regionPurchases = Math.round(purchases * w);
      const regionRevenue = revenue * w;
      return {
        region: r.region,
        purchases: regionPurchases,
        revenue: regionRevenue,
        national_share: Number((w * 100).toFixed(2)),
        avg_ticket: regionPurchases > 0 ? regionRevenue / regionPurchases : 0,
        conversion: cfg.conversion * (0.85 + rng() * 0.35),
        active_users: Math.round(activeUsers * w),
      };
    }).sort((a, b) => b.purchases - a.purchases);
  }

  private buildFunnel() {
    const views = Math.round(this.totalViews);
    const carts = Math.round(this.totalCarts);
    const checkouts = Math.round(this.totalCheckouts);
    const purchases = Math.round(this.totalPurchases);
    const stages = [
      { stage: "Visualización de producto", key: "VIEW_PRODUCT", value: views },
      { stage: "Agregado al carrito", key: "ADD_TO_CART", value: carts },
      { stage: "Inicio de compra", key: "CHECKOUT_STARTED", value: checkouts },
      { stage: "Compra confirmada", key: "PURCHASE", value: purchases },
    ];
    return stages.map((s, i) => ({
      ...s,
      drop_from_previous:
        i === 0 || stages[i - 1].value === 0
          ? 0
          : Number((((stages[i - 1].value - s.value) / stages[i - 1].value) * 100).toFixed(2)),
    }));
  }

  private buildInfrastructure(latency: number): InfrastructureStatus[] {
    const cfg = this.cfg();
    return INFRA_SEED.map((c, i) => {
      const rng = createRng(hashString(c.id + this.scenario) + this.tick);
      const pressure = cfg.alertRate;
      const roll = rng();
      const status: InfrastructureStatus["status"] =
        roll < pressure * 0.12 ? "DESCONECTADO" : roll < pressure * 0.6 ? "DEGRADADO" : "OPERATIVO";
      return {
        id: c.id,
        name: c.name,
        status,
        latency_ms: Math.round(latency * (0.35 + i * 0.14) * (0.85 + rng() * 0.3)),
        last_heartbeat: new Date(Date.now() - Math.floor(rng() * 6) * 1000).toISOString(),
        messages_processed: Math.round(this.totalEvents * (1 - i * 0.06)),
        errors: Math.round(this.failedPayments * (0.1 + i * 0.03) * rng()),
        responsibility: c.responsibility,
        inputs: c.inputs,
        outputs: c.outputs,
      };
    });
  }

  private buildProfiles(activeUsers: number, purchases: number, revenue: number): ProfileMetric[] {
    return AGENT_PROFILES.map((profile) => {
      const w = PROFILE_WEIGHTS[profile];
      const rng = createRng(hashString(profile + this.scenario));
      const users = Math.round(activeUsers * w);
      const profilePurchases = Math.round(purchases * w * (0.6 + rng()));
      return {
        profile,
        users,
        purchases: profilePurchases,
        conversion: users > 0 ? profilePurchases / Math.max(1, users * 3) : 0,
        revenue: revenue * w * (0.7 + rng() * 0.6),
      };
    }).sort((a, b) => b.users - a.users);
  }

  private buildSources(): SourceMetric[] {
    return SOURCES.map((source) => ({
      source,
      events: Math.round(this.totalEvents * SOURCE_SHARES[source]),
      share: Number((SOURCE_SHARES[source] * 100).toFixed(1)),
    }));
  }
}

/** Resultados consolidados por escenario para la página de experimentos. */
export function buildScenarioResults(scenarios: Scenario[]): ScenarioResult[] {
  return scenarios.map((scenario) => {
    const cfg = SCENARIO_CONFIG[scenario];
    const rng = createRng(hashString("resultado" + scenario));
    const durationSeconds = 900;
    const avgEps = (cfg.epsMin + cfg.epsMax) / 2;
    const totalEvents = Math.round(avgEps * durationSeconds);
    const views = totalEvents * EVENT_WEIGHTS.VIEW_PRODUCT;
    const purchases = Math.round(views * cfg.conversion);
    const carts = Math.round(totalEvents * EVENT_WEIGHTS.ADD_TO_CART);
    const alerts = Math.round(6 + cfg.alertRate * 95);
    return {
      scenario,
      total_events: totalEvents,
      avg_eps: Number(avgEps.toFixed(1)),
      peak_eps: Number((cfg.epsMax * (1 + rng() * 0.06)).toFixed(1)),
      max_active_users: Math.round(cfg.epsMax * 6.4),
      purchases,
      conversion: cfg.conversion,
      total_revenue: purchases * cfg.ticket,
      abandoned_carts: Math.max(0, carts - purchases),
      failed_payments: Math.round(purchases * cfg.failedPaymentRate),
      avg_latency_ms: cfg.latency,
      alerts,
      critical_alerts: Math.round(alerts * (0.18 + cfg.alertRate * 0.5)),
    };
  });
}
