/**
 * Motor de análisis del lado del cliente: insights automáticos, resumen del
 * sistema, detección de anomalías, heatmap de eventos y conclusiones de
 * experimentos. Todo se calcula por reglas a partir de los datos actuales.
 */
import type {
  DashboardMetrics,
  EventTypeIntervalMatrix,
  EventType,
  ProductMetric,
  ScenarioResult,
  ThroughputPoint,
} from "@/types";
import { EVENT_WEIGHTS, SCENARIO_CONFIG } from "@/data/catalog";
import { formatInt, formatPercent, formatCompactCurrency } from "@/utils/format";

export type InsightTone = "positivo" | "neutral" | "advertencia" | "critico";

export interface Insight {
  id: string;
  tone: InsightTone;
  title: string;
  detail: string;
}

export interface AnomalyPoint {
  index: number;
  point: ThroughputPoint;
  z: number;
  kind: "pico" | "caida";
}

export interface SeriesStats {
  min: number;
  max: number;
  avg: number;
  std: number;
  minIndex: number;
  maxIndex: number;
  trendPct: number;
}

export function seriesStats(values: number[]): SeriesStats | null {
  if (!values.length) return null;
  const avg = values.reduce((a, b) => a + b, 0) / values.length;
  const std = Math.sqrt(values.reduce((a, b) => a + (b - avg) ** 2, 0) / values.length);
  let minIndex = 0;
  let maxIndex = 0;
  values.forEach((v, i) => {
    if (v < values[minIndex]) minIndex = i;
    if (v > values[maxIndex]) maxIndex = i;
  });
  const half = Math.max(1, Math.floor(values.length / 2));
  const first = values.slice(0, half).reduce((a, b) => a + b, 0) / half;
  const second = values.slice(-half).reduce((a, b) => a + b, 0) / half;
  return {
    min: values[minIndex],
    max: values[maxIndex],
    avg,
    std,
    minIndex,
    maxIndex,
    trendPct: first === 0 ? 0 : ((second - first) / first) * 100,
  };
}

/** Detecta picos y caídas usando desviaciones respecto a la media móvil. */
export function detectAnomalies(points: ThroughputPoint[], threshold = 1.9): AnomalyPoint[] {
  const values = points.map((p) => p.eps);
  const stats = seriesStats(values);
  if (!stats || stats.std < 1e-6) return [];
  const out: AnomalyPoint[] = [];
  values.forEach((v, index) => {
    const z = (v - stats.avg) / stats.std;
    if (Math.abs(z) >= threshold) {
      out.push({ index, point: points[index], z, kind: z > 0 ? "pico" : "caida" });
    }
  });
  return out;
}

/** Compara la mitad reciente contra la mitad anterior de la ventana visible. */
export function periodComparison(values: number[]): { current: number; previous: number; pct: number } {
  if (values.length < 2) return { current: values[0] ?? 0, previous: values[0] ?? 0, pct: 0 };
  const half = Math.floor(values.length / 2);
  const previous = values.slice(0, half).reduce((a, b) => a + b, 0) / Math.max(1, half);
  const current = values.slice(half).reduce((a, b) => a + b, 0) / Math.max(1, values.length - half);
  return { current, previous, pct: previous === 0 ? 0 : ((current - previous) / previous) * 100 };
}

const RANGE_LABEL: Record<string, string> = {
  "5m": "los últimos cinco minutos",
  "15m": "los últimos quince minutos",
  "1h": "la última hora",
  all: "toda la ejecución",
};

/** Frase ejecutiva generada por reglas a partir del snapshot vigente. */
export function buildSystemSummary(
  snapshot: DashboardMetrics | null,
  throughput: ThroughputPoint[],
  timeRange: string,
): string {
  if (!snapshot) return "Esperando el primer snapshot del backend consumidor.";
  const cfg = SCENARIO_CONFIG[snapshot.scenario];
  const comp = periodComparison(throughput.map((p) => p.eps));
  const dir = comp.pct >= 0 ? "un incremento" : "una reducción";
  const conv = snapshot.metrics.purchase_conversion * 100;
  const convDelta = snapshot.deltas.purchase_conversion;
  const convText =
    Math.abs(convDelta) < 1
      ? `La conversión se mantiene estable en ${conv.toFixed(2)} %`
      : `La conversión ${convDelta > 0 ? "subió" : "cayó"} ${Math.abs(convDelta).toFixed(1)} % hasta ${conv.toFixed(2)} %`;
  const topRegion = snapshot.regions[0];
  const failed = snapshot.events_by_type.find((e) => e.event_type === "PAYMENT_FAILED");
  const critical = snapshot.alerts.filter((a) => a.level === "CRITICAL" && a.status === "ACTIVA").length;
  const riskText = critical
    ? `Hay ${critical} alerta${critical === 1 ? "" : "s"} crítica${critical === 1 ? "" : "s"} activa${critical === 1 ? "" : "s"}`
    : failed && failed.percentage > 1.2
      ? `Los pagos rechazados representan ${failed.percentage.toFixed(1)} % del flujo${topRegion ? `, con mayor concentración en ${topRegion.region}` : ""}`
      : "No se registran incidencias críticas en el clúster";
  return `Durante ${RANGE_LABEL[timeRange] ?? "la ventana observada"} el escenario ${cfg.label} registró ${dir} de ${Math.abs(comp.pct).toFixed(1)} % en el throughput, con ${snapshot.metrics.events_per_second.toFixed(0)} eventos por segundo. ${convText}. ${riskText}.`;
}

/** Insights automáticos por reglas para las páginas principales. */
export function buildInsights(
  snapshot: DashboardMetrics | null,
  throughput: ThroughputPoint[],
  scope: "general" | "audiencias" | "eventos" | "productos" | "regiones" | "alertas" = "general",
): Insight[] {
  if (!snapshot) return [];
  const out: Insight[] = [];
  const push = (i: Insight) => out.push(i);

  if (scope === "general" || scope === "audiencias") {
    const growing = [...snapshot.audiences].sort((a, b) => b.change - a.change)[0];
    if (growing) {
      push({
        id: "aud-crecimiento",
        tone: growing.change >= 0 ? "positivo" : "advertencia",
        title: `${growing.label} ${growing.change >= 0 ? "creció" : "retrocedió"} ${Math.abs(growing.change).toFixed(1)} %`,
        detail: `Concentra ${formatInt(growing.users)} usuarios (${formatPercent(growing.percentage)} de la base segmentada).`,
      });
    }
    const risky = snapshot.audiences.find((a) => a.id === "riesgo-abandono" || a.id === "abandono-carrito");
    if (risky) {
      push({
        id: "aud-riesgo",
        tone: risky.change > 5 ? "critico" : "advertencia",
        title: `${risky.label} agrupa ${formatInt(risky.users)} usuarios`,
        detail: `Variación de ${risky.change.toFixed(1)} % respecto a la ventana anterior. Prioridad ${risky.priority}.`,
      });
    }
  }

  if (scope === "general" || scope === "regiones") {
    const top = snapshot.regions[0];
    if (top) {
      push({
        id: "reg-top",
        tone: "neutral",
        title: `El ${top.national_share.toFixed(1)} % de las compras proviene de ${top.region}`,
        detail: `${formatInt(top.purchases)} compras y ${formatCompactCurrency(top.revenue)} en ingresos, con conversión de ${(top.conversion * 100).toFixed(2)} %.`,
      });
    }
    const best = [...snapshot.regions].sort((a, b) => b.conversion - a.conversion)[0];
    if (best && top && best.region !== top.region) {
      push({
        id: "reg-conv",
        tone: "positivo",
        title: `${best.region} lidera en conversión con ${(best.conversion * 100).toFixed(2)} %`,
        detail: `Supera el promedio nacional pese a concentrar solo ${best.national_share.toFixed(1)} % del volumen.`,
      });
    }
  }

  if (scope === "general" || scope === "productos") {
    const withConv = snapshot.top_viewed_products.map((p) => ({
      ...p,
      conv: p.views > 0 ? p.units / p.views : 0,
    }));
    const avgConv = withConv.reduce((a, b) => a + b.conv, 0) / Math.max(1, withConv.length);
    const leak = withConv.filter((p) => p.conv < avgConv * 0.75).sort((a, b) => b.views - a.views)[0];
    if (leak) {
      push({
        id: "prod-fuga",
        tone: "advertencia",
        title: `${leak.name} tiene muchas visitas y conversión inferior al promedio`,
        detail: `${formatInt(leak.views)} visitas con conversión de ${(leak.conv * 100).toFixed(2)} % frente a ${(avgConv * 100).toFixed(2)} % del catálogo.`,
      });
    }
    const star = [...snapshot.top_purchased_products].sort((a, b) => b.revenue - a.revenue)[0];
    if (star) {
      push({
        id: "prod-estrella",
        tone: "positivo",
        title: `${star.name} lidera los ingresos con ${formatCompactCurrency(star.revenue)}`,
        detail: `${formatInt(star.units)} unidades vendidas en ${formatInt(star.orders)} órdenes.`,
      });
    }
  }

  if (scope === "general" || scope === "eventos") {
    const anomalies = detectAnomalies(throughput);
    const peak = anomalies.filter((a) => a.kind === "pico").sort((a, b) => b.z - a.z)[0];
    if (peak) {
      push({
        id: "evt-pico",
        tone: "advertencia",
        title: `Pico de ${peak.point.eps.toFixed(0)} eps registrado a las ${peak.point.label}`,
        detail: `Se desvía ${peak.z.toFixed(1)}σ del promedio de la ventana observada.`,
      });
    }
    const failed = snapshot.events_by_type.find((e) => e.event_type === "PAYMENT_FAILED");
    if (failed) {
      push({
        id: "evt-pagos",
        tone: failed.percentage > 1.5 ? "critico" : "neutral",
        title: `Los pagos rechazados representan ${failed.percentage.toFixed(2)} % del flujo`,
        detail: `${formatInt(failed.count)} eventos PAYMENT_FAILED acumulados en el escenario activo.`,
      });
    }
  }

  if (scope === "general" || scope === "alertas") {
    const activas = snapshot.alerts.filter((a) => a.status === "ACTIVA");
    const byComponent = new Map<string, number>();
    activas.forEach((a) => byComponent.set(a.component, (byComponent.get(a.component) ?? 0) + 1));
    const worst = [...byComponent.entries()].sort((a, b) => b[1] - a[1])[0];
    if (worst) {
      push({
        id: "alr-componente",
        tone: worst[1] > 2 ? "critico" : "advertencia",
        title: `${worst[0]} concentra ${worst[1]} alertas activas`,
        detail: `De un total de ${activas.length} alertas sin resolver en el escenario ${SCENARIO_CONFIG[snapshot.scenario].label}.`,
      });
    }
  }

  return out.slice(0, scope === "general" ? 4 : 3);
}

export interface HeatmapCell {
  eventType: EventType;
  bucket: string;
  value: number;
  intensity: number;
}

export interface HeatmapData {
  buckets: string[];
  rows: Array<{ eventType: EventType; cells: HeatmapCell[]; total: number }>;
  max: number;
}

/** Construye el heatmap tipo de evento × intervalo a partir del throughput. */
export function buildHeatmap(
  throughput: ThroughputPoint[],
  eventTypes: readonly EventType[],
  bucketCount = 12,
): HeatmapData {
  if (throughput.length === 0) {
    return { buckets: [], rows: eventTypes.map((e) => ({ eventType: e, cells: [], total: 0 })), max: 0 };
  }
  const size = Math.max(1, Math.ceil(throughput.length / bucketCount));
  const groups: ThroughputPoint[][] = [];
  for (let i = 0; i < throughput.length; i += size) groups.push(throughput.slice(i, i + size));
  const buckets = groups.map((g) => g[0].label.slice(0, 5));
  let max = 0;
  const rows = eventTypes.map((eventType) => {
    const weight = EVENT_WEIGHTS[eventType];
    const cells = groups.map((g, gi) => {
      const eps = g.reduce((a, p) => a + p.eps, 0) / g.length;
      const seasonal = 1 + Math.sin(gi / 2.1 + weight * 31) * 0.22;
      const value = Math.round(eps * weight * g.length * 1.5 * seasonal);
      max = Math.max(max, value);
      return { eventType, bucket: buckets[gi], value, intensity: 0 };
    });
    return { eventType, cells, total: cells.reduce((a, c) => a + c.value, 0) };
  });
  rows.forEach((r) => r.cells.forEach((c) => (c.intensity = max === 0 ? 0 : c.value / max)));
  return { buckets, rows, max };
}

/** Construye el heatmap desde conteos reales event_type × intervalo enviados por el backend. */
export function buildHeatmapFromIntervals(matrix?: EventTypeIntervalMatrix): HeatmapData | null {
  if (!matrix || matrix.buckets.length === 0 || matrix.rows.length === 0) return null;
  let max = 0;
  const rows = matrix.rows.map((row) => {
    const cells = row.cells.map((cell) => {
      const value = Number(cell.value || 0);
      max = Math.max(max, value);
      return {
        eventType: row.event_type,
        bucket: cell.bucket,
        value,
        intensity: 0,
      };
    });
    return { eventType: row.event_type, cells, total: cells.reduce((a, c) => a + c.value, 0) };
  });
  rows.forEach((row) => row.cells.forEach((cell) => (cell.intensity = max === 0 ? 0 : cell.value / max)));
  return { buckets: matrix.buckets, rows, max };
}

export type Quadrant = "estrella" | "fuga" | "oculto" | "bajo";

export const QUADRANT_META: Record<Quadrant, { label: string; description: string; color: string }> = {
  estrella: {
    label: "Productos estrella",
    description: "Alta exposición y alta conversión.",
    color: "var(--color-success)",
  },
  fuga: {
    label: "Alta visita, baja compra",
    description: "Mucho tráfico que no convierte: revisar precio o ficha.",
    color: "var(--color-warning)",
  },
  oculto: {
    label: "Baja exposición, buena conversión",
    description: "Candidatos a mayor promoción.",
    color: "var(--color-info)",
  },
  bajo: {
    label: "Bajo desempeño",
    description: "Poca visibilidad y poca conversión.",
    color: "var(--color-muted-foreground)",
  },
};

export interface ProductPoint extends ProductMetric {
  conversion: number;
  quadrant: Quadrant;
}

export function buildProductMatrix(products: ProductMetric[]): {
  points: ProductPoint[];
  avgConversion: number;
  avgViews: number;
} {
  const enriched = products.map((p) => ({
    ...p,
    conversion: p.views > 0 ? p.units / p.views : 0,
  }));
  const avgConversion =
    enriched.reduce((a, b) => a + b.conversion, 0) / Math.max(1, enriched.length);
  const avgViews = enriched.reduce((a, b) => a + b.views, 0) / Math.max(1, enriched.length);
  const points = enriched.map((p) => {
    const highConv = p.conversion >= avgConversion;
    const highViews = p.views >= avgViews;
    const quadrant: Quadrant = highConv
      ? highViews
        ? "estrella"
        : "oculto"
      : highViews
        ? "fuga"
        : "bajo";
    return { ...p, quadrant };
  });
  return { points, avgConversion, avgViews };
}

/** Conclusiones automáticas de la comparación de escenarios. */
export function scenarioConclusions(results: ScenarioResult[]): string[] {
  if (results.length < 2) return ["Selecciona al menos dos escenarios para generar conclusiones."];
  const label = (s: ScenarioResult) => SCENARIO_CONFIG[s.scenario].label;
  const byEps = [...results].sort((a, b) => b.avg_eps - a.avg_eps);
  const byConv = [...results].sort((a, b) => b.conversion - a.conversion);
  const byLat = [...results].sort((a, b) => a.avg_latency_ms - b.avg_latency_ms);
  const byAlerts = [...results].sort((a, b) => b.alerts - a.alerts);
  const byRevenue = [...results].sort((a, b) => b.total_revenue - a.total_revenue);
  const epsRatio = byEps[0].avg_eps / Math.max(1, byEps[byEps.length - 1].avg_eps);
  const latRatio = byLat[byLat.length - 1].avg_latency_ms / Math.max(1, byLat[0].avg_latency_ms);
  return [
    `${label(byEps[0])} sostiene el mayor throughput con ${byEps[0].avg_eps.toFixed(1)} eps promedio, ${epsRatio.toFixed(1)}× el escenario de menor carga (${label(byEps[byEps.length - 1])}).`,
    `${label(byConv[0])} obtiene la mejor conversión (${(byConv[0].conversion * 100).toFixed(2)} %), mientras ${label(byConv[byConv.length - 1])} se queda en ${(byConv[byConv.length - 1].conversion * 100).toFixed(2)} %.`,
    `La latencia crece ${latRatio.toFixed(1)}× entre ${label(byLat[0])} (${byLat[0].avg_latency_ms} ms) y ${label(byLat[byLat.length - 1])} (${byLat[byLat.length - 1].avg_latency_ms} ms), lo que evidencia el costo de la contrapresión en el clúster.`,
    `${label(byAlerts[0])} genera ${byAlerts[0].alerts} alertas (${byAlerts[0].critical_alerts} críticas): es el escenario con mayor exigencia de observabilidad.`,
    `El mayor ingreso simulado corresponde a ${label(byRevenue[0])} con ${formatCompactCurrency(byRevenue[0].total_revenue)}, pese a no ser siempre el de mejor conversión.`,
  ];
}

/** Normalización 0-100 para el radar de experimentos. */
export function normalizeForRadar(results: ScenarioResult[]) {
  const metrics: Array<{ key: string; label: string; get: (r: ScenarioResult) => number; invert?: boolean }> = [
    { key: "eps", label: "Throughput", get: (r) => r.avg_eps },
    { key: "conv", label: "Conversión", get: (r) => r.conversion },
    { key: "rev", label: "Ingresos", get: (r) => r.total_revenue },
    { key: "lat", label: "Latencia", get: (r) => r.avg_latency_ms, invert: true },
    { key: "alr", label: "Estabilidad", get: (r) => r.alerts, invert: true },
    { key: "usr", label: "Usuarios", get: (r) => r.max_active_users },
  ];
  return metrics.map((m) => {
    const values = results.map(m.get);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const row: Record<string, string | number> = { metric: m.label };
    results.forEach((r) => {
      const raw = m.get(r);
      const norm = max === min ? 100 : ((raw - min) / (max - min)) * 100;
      row[r.scenario] = Number((m.invert ? 100 - norm : norm).toFixed(1));
    });
    return row;
  });
}
