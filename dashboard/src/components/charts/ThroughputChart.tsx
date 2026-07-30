import { useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceArea,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Panel } from "@/components/common/Panel";
import { ChartSkeleton, EmptyState } from "@/components/common/States";
import { useRealtimeDashboard } from "@/hooks/useRealtimeDashboard";
import { formatEps, formatInt } from "@/utils/format";
import { detectAnomalies, periodComparison, seriesStats } from "@/lib/analytics";
import { SCENARIO_CONFIG } from "@/data/catalog";
import { CHART_TOOLTIP_STYLE } from "@/lib/palette";
import type { ThroughputPoint } from "@/types";

const RANGE_POINTS: Record<string, number> = { "5m": 40, "15m": 100, "1h": 200, all: 240 };

/** Tooltip enriquecido: eps, compras acumuladas y comparación contra el promedio. */
function ThroughputTooltip({
  active,
  payload,
  avg,
}: {
  active?: boolean;
  payload?: Array<{ payload: ThroughputPoint }>;
  avg: number;
}) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  const diff = avg === 0 ? 0 : ((p.eps - avg) / avg) * 100;
  return (
    <div style={CHART_TOOLTIP_STYLE} className="px-3 py-2">
      <p className="font-medium text-foreground">Hora {p.label}</p>
      <p className="mt-1 text-muted-foreground">
        Throughput: <strong className="text-foreground">{formatEps(p.eps)}</strong>
      </p>
      <p className="text-muted-foreground">
        Compras acumuladas: <strong className="text-foreground">{formatInt(p.purchases)}</strong>
      </p>
      <p className="text-muted-foreground">
        {diff >= 0 ? "+" : ""}
        {diff.toFixed(1)} % frente al promedio de la ventana
      </p>
    </div>
  );
}

/** Indicadores 2 y 8: eventos por segundo y tendencia temporal. */
export function ThroughputChart({ compact = false }: { compact?: boolean }) {
  const { throughput, loading, filters, setFilters, snapshot } = useRealtimeDashboard();

  const data = useMemo(() => {
    const limit = RANGE_POINTS[filters.timeRange] ?? 60;
    return throughput.slice(-limit);
  }, [throughput, filters.timeRange]);

  const stats = useMemo(() => seriesStats(data.map((d) => d.eps)), [data]);
  const comparison = useMemo(() => periodComparison(data.map((d) => d.eps)), [data]);
  const anomalies = useMemo(() => detectAnomalies(data), [data]);

  // Banda de rango esperado: usa eps min/max del escenario activo si existe, si no avg ± σ.
  const cfg = snapshot ? SCENARIO_CONFIG[snapshot.scenario] : null;
  const band = useMemo(() => {
    if (cfg) return { low: cfg.epsMin, high: cfg.epsMax };
    if (!stats) return null;
    return { low: Math.max(0, stats.avg - stats.std), high: stats.avg + stats.std };
  }, [cfg, stats]);

  const windowActive = filters.window;

  const handlePointClick = (label: string) => {
    const idx = data.findIndex((d) => d.label === label);
    if (idx === -1) return;
    if (windowActive) {
      setFilters({ window: null });
      return;
    }
    const fromIdx = Math.max(0, idx - 3);
    const toIdx = Math.min(data.length - 1, idx + 3);
    setFilters({ window: { from: data[fromIdx].label, to: data[toIdx].label } });
  };

  const height = compact ? 200 : 300;

  return (
    <Panel
      level="primary"
      title="Actividad de eventos en tiempo real"
      description="Throughput consolidado por Apache Flink sobre los topics de entrada"
      tooltip="Eventos por segundo (eps) en ventanas deslizantes de un segundo. La banda sombreada representa el rango esperado del escenario activo y los puntos marcados son anomalías (picos o caídas) respecto al promedio."
      actions={
        stats && (
          <div className="flex flex-wrap gap-3 text-xs tabular-nums text-muted-foreground">
            <span>
              Mín <strong className="text-foreground">{stats.min.toFixed(1)}</strong>
            </span>
            <span>
              Prom <strong className="text-info">{stats.avg.toFixed(1)}</strong>
            </span>
            <span>
              Máx <strong className="text-warning">{stats.max.toFixed(1)}</strong>
            </span>
            <span>
              Variación{" "}
              <strong className={comparison.pct >= 0 ? "text-success" : "text-critical"}>
                {comparison.pct >= 0 ? "+" : ""}
                {comparison.pct.toFixed(1)} %
              </strong>
            </span>
            {windowActive && (
              <button
                type="button"
                onClick={() => setFilters({ window: null })}
                className="rounded border border-panel-border px-2 py-0.5 text-foreground hover:bg-muted"
              >
                Limpiar ventana {windowActive.from}–{windowActive.to}
              </button>
            )}
          </div>
        )
      }
    >
      {loading ? (
        <ChartSkeleton height={height} />
      ) : data.length < 2 ? (
        <EmptyState
          title="Recolectando muestras"
          description="El gráfico se dibuja al recibir al menos dos actualizaciones del backend."
        />
      ) : (
        <div style={{ height }} className="w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={data}
              margin={{ top: 8, right: 8, left: -12, bottom: 0 }}
              onClick={(state) => {
                const label = state?.activeLabel;
                if (typeof label === "string") handlePointClick(label);
              }}
            >
              <defs>
                <linearGradient id="epsFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--color-info)" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="var(--color-info)" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }}
                minTickGap={40}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }}
                axisLine={false}
                tickLine={false}
                width={48}
              />
              <RTooltip content={<ThroughputTooltip avg={stats?.avg ?? 0} />} cursor={{ stroke: "var(--color-info)", strokeOpacity: 0.3 }} />
              {band && (
                <ReferenceArea
                  y1={band.low}
                  y2={band.high}
                  fill="var(--color-success)"
                  fillOpacity={0.08}
                  stroke="var(--color-success)"
                  strokeOpacity={0.2}
                  strokeDasharray="2 2"
                  ifOverflow="extendDomain"
                  label={{ value: "Rango esperado", position: "insideTopLeft", fill: "var(--color-success)", fontSize: 10 }}
                />
              )}
              {windowActive && (
                <ReferenceArea
                  x1={windowActive.from}
                  x2={windowActive.to}
                  fill="var(--color-primary)"
                  fillOpacity={0.12}
                  ifOverflow="extendDomain"
                />
              )}
              {stats && (
                <ReferenceLine
                  y={stats.avg}
                  stroke="var(--color-warning)"
                  strokeDasharray="4 4"
                  label={{
                    value: `Promedio ${stats.avg.toFixed(1)} eps`,
                    position: "insideTopRight",
                    fill: "var(--color-warning)",
                    fontSize: 11,
                  }}
                />
              )}
              <Area
                type="monotone"
                dataKey="eps"
                stroke="var(--color-info)"
                strokeWidth={2}
                fill="url(#epsFill)"
                animationDuration={400}
                dot={false}
                cursor="pointer"
              />
              {anomalies.map((a) => (
                <ReferenceDot
                  key={a.index}
                  x={a.point.label}
                  y={a.point.eps}
                  r={4}
                  fill={a.kind === "pico" ? "var(--color-warning)" : "var(--color-critical)"}
                  stroke="var(--color-background)"
                  strokeWidth={1.5}
                  label={{
                    value: `${a.z >= 0 ? "+" : ""}${a.z.toFixed(1)}σ`,
                    position: "top",
                    fill: a.kind === "pico" ? "var(--color-warning)" : "var(--color-critical)",
                    fontSize: 10,
                  }}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </Panel>
  );
}
