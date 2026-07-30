/**
 * Vista regional: mapa coroplético (izquierda) + ranking de barras (derecha),
 * sincronizados por el mismo filtro cruzado y selector de métrica.
 */
import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Panel } from "@/components/common/Panel";
import { ChartSkeleton } from "@/components/common/States";
import { InsightCard } from "@/components/common/Cards";
import { Button } from "@/components/ui/button";
import { useRealtimeDashboard } from "@/hooks/useRealtimeDashboard";
import { PeruMap, type MapMetric } from "@/components/charts/PeruMap";
import { buildInsights } from "@/lib/analytics";
import {
  formatCompactCurrency,
  formatCurrency,
  formatInt,
  formatPercent,
  formatRatioAsPercent,
} from "@/utils/format";

const METRICS: Array<{ key: MapMetric; label: string; color: string }> = [
  { key: "purchases", label: "Compras", color: "var(--color-success)" },
  { key: "revenue", label: "Ingresos", color: "var(--color-info)" },
  { key: "conversion", label: "Conversión", color: "var(--color-special)" },
  { key: "active_users", label: "Usuarios activos", color: "var(--color-warning)" },
];

/** Indicador 7: compras por región, con mapa y ranking sincronizados. */
export function RegionChart({ withTable = true }: { withTable?: boolean }) {
  const { snapshot, throughput, loading, filters, setFilters } = useRealtimeDashboard();
  const [metric, setMetric] = useState<MapMetric>("purchases");
  const active = METRICS.find((m) => m.key === metric)!;
  const data = [...(snapshot?.regions ?? [])].sort((a, b) => b[metric] - a[metric]);
  const insights = buildInsights(snapshot, throughput, "regiones");

  const toggle = (region: string) => setFilters({ region: filters.region === region ? "TODAS" : region });

  const formatValue = (value: number) => {
    if (metric === "revenue") return formatCurrency(value);
    if (metric === "conversion") return formatRatioAsPercent(value);
    return formatInt(value);
  };

  return (
    <Panel
      level="primary"
      title="Compras por región"
      description="Distribución territorial de la actividad comercial simulada en el Perú"
      tooltip="Los eventos incluyen la región de origen en el sobre común; Flink agrega por región y calcula ticket promedio y participación nacional."
      actions={
        <div className="flex flex-wrap gap-1" role="group" aria-label="Métrica regional">
          {METRICS.map((m) => (
            <Button
              key={m.key}
              size="sm"
              variant={metric === m.key ? "secondary" : "ghost"}
              className="h-7 px-2 text-xs"
              onClick={() => setMetric(m.key)}
            >
              {m.label}
            </Button>
          ))}
        </div>
      }
    >
      {loading ? (
        <ChartSkeleton height={320} />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <PeruMap regions={snapshot?.regions ?? []} metric={metric} selected={filters.region} onSelect={toggle} />

            <div className="h-[320px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data} layout="vertical" margin={{ top: 4, right: 24, left: 8, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
                  <XAxis
                    type="number"
                    tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    type="category"
                    dataKey="region"
                    width={96}
                    tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <RTooltip
                    cursor={{ fill: "var(--color-muted)", opacity: 0.35 }}
                    contentStyle={{
                      background: "var(--color-popover)",
                      border: "1px solid var(--color-border)",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    formatter={(value: number) => [formatValue(value), active.label]}
                  />
                  <Bar
                    dataKey={metric}
                    radius={[0, 4, 4, 0]}
                    animationDuration={400}
                    onClick={(d: unknown) => toggle((d as { region: string }).region)}
                    style={{ cursor: "pointer" }}
                    fill={active.color}
                    fillOpacity={1}
                    shape={(props: any) => {
                      const selected = filters.region === "TODAS" || filters.region === props.payload.region;
                      return (
                        <rect
                          x={props.x}
                          y={props.y}
                          width={props.width}
                          height={props.height}
                          rx={4}
                          fill={active.color}
                          fillOpacity={selected ? 1 : 0.25}
                        />
                      );
                    }}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {insights.length > 0 && (
            <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
              {insights.slice(0, 2).map((i) => (
                <InsightCard key={i.id} insight={i} />
              ))}
            </div>
          )}

          {withTable && (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-panel-border text-left text-[11px] uppercase tracking-wide text-muted-foreground">
                    <th className="py-2 pr-2 font-medium">Región</th>
                    <th className="px-2 py-2 text-right font-medium">Compras</th>
                    <th className="px-2 py-2 text-right font-medium">Ingresos</th>
                    <th className="px-2 py-2 text-right font-medium">% nacional</th>
                    <th className="py-2 pl-2 text-right font-medium">Ticket promedio</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((r) => (
                    <tr
                      key={r.region}
                      className="cursor-pointer border-b border-panel-border/60 last:border-0 hover:bg-muted/30"
                      onClick={() => toggle(r.region)}
                    >
                      <td className="py-2 pr-2 font-medium">{r.region}</td>
                      <td className="px-2 py-2 text-right tabular-nums">{formatInt(r.purchases)}</td>
                      <td className="px-2 py-2 text-right tabular-nums">
                        {formatCompactCurrency(r.revenue)}
                      </td>
                      <td className="px-2 py-2 text-right tabular-nums">{formatPercent(r.national_share)}</td>
                      <td className="py-2 pl-2 text-right tabular-nums">{formatCurrency(r.avg_ticket)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </Panel>
  );
}
