import { useMemo, useState } from "react";
import { TrendingDown } from "lucide-react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Panel } from "@/components/common/Panel";
import { ChartSkeleton, PanelSkeleton } from "@/components/common/States";
import { InsightCard } from "@/components/common/Cards";
import { Badge } from "@/components/ui/badge";
import { useRealtimeDashboard } from "@/hooks/useRealtimeDashboard";
import { periodComparison } from "@/lib/analytics";
import { CHART_TOOLTIP_STYLE } from "@/lib/palette";
import { formatInt, formatPercent, formatRatioAsPercent, formatTime } from "@/utils/format";
import { cn } from "@/lib/utils";
import type { Insight } from "@/lib/analytics";

/** Indicador 9: conversión de compras — embudo interactivo + evolución. */
export function ConversionPanel() {
  const { snapshot, loading, filters, setFilters } = useRealtimeDashboard();
  const c = snapshot?.conversion;
  const [hover, setHover] = useState<string | null>(null);

  const maxStage = c ? Math.max(1, ...c.funnel.map((f) => f.value)) : 1;
  const firstStage = c?.funnel[0]?.value ?? 1;
  const diff = c ? (c.overall - c.previous_overall) * 100 : 0;

  // Insights propios: mayor fuga del embudo y comparación vs promedio de ventana.
  const insights = useMemo<Insight[]>(() => {
    if (!c) return [];
    const out: Insight[] = [];
    const worst = [...c.funnel].sort((a, b) => b.drop_from_previous - a.drop_from_previous)[0];
    if (worst && worst.drop_from_previous > 0) {
      out.push({
        id: "conv-fuga",
        tone: worst.drop_from_previous > 40 ? "critico" : "advertencia",
        title: `Mayor fuga en "${worst.stage}"`,
        detail: `Pierde ${formatPercent(worst.drop_from_previous)} de los usuarios respecto a la etapa anterior del embudo.`,
      });
    }
    const stats = periodComparison(c.history.map((h) => h.value));
    out.push({
      id: "conv-vs-promedio",
      tone: stats.pct >= 0 ? "positivo" : "advertencia",
      title: `Conversión actual ${stats.pct >= 0 ? "por encima" : "por debajo"} del promedio de la ventana`,
      detail: `${stats.current.toFixed(2)} % frente a ${stats.previous.toFixed(2)} % de la primera mitad observada (${stats.pct >= 0 ? "+" : ""}${stats.pct.toFixed(1)} %).`,
    });
    return out;
  }, [c]);

  const toggleStage = (key: string) => {
    setFilters({ funnelStage: filters.funnelStage === key ? "TODAS" : key });
  };

  const activeStage = c?.funnel.find((f) => f.key === filters.funnelStage);

  return (
    <Panel
      title="Conversión de compras"
      description="Embudo VIEW_PRODUCT → ADD_TO_CART → inicio de compra → PURCHASE"
      tooltip="La conversión total es la razón entre compras confirmadas y visualizaciones de producto acumuladas en el escenario activo. Haz clic en una etapa para filtrar el resto del dashboard."
    >
      {loading || !c ? (
        <PanelSkeleton rows={6} />
      ) : (
        <div className="space-y-5">
          <div className="grid gap-5 lg:grid-cols-2">
            {/* Embudo interactivo tipo segmentos trapezoidales apilados */}
            <div className="space-y-2">
              <div className="grid grid-cols-3 gap-2">
                <Stat label="Vista → carrito" value={formatRatioAsPercent(c.view_to_cart)} />
                <Stat label="Carrito → compra" value={formatRatioAsPercent(c.cart_to_purchase)} />
                <Stat label="Conversión total" value={formatRatioAsPercent(c.overall)} highlight />
              </div>
              <p className="text-xs text-muted-foreground">
                Frente al periodo anterior ({formatRatioAsPercent(c.previous_overall)}):{" "}
                <strong className={diff >= 0 ? "text-success" : "text-critical"}>
                  {diff >= 0 ? "+" : ""}
                  {diff.toFixed(2)} puntos porcentuales
                </strong>
              </p>

              <ul className="space-y-1.5">
                {c.funnel.map((stage, i) => {
                  const widthPct = Math.max(18, (stage.value / maxStage) * 100);
                  const nextWidthPct =
                    i < c.funnel.length - 1
                      ? Math.max(18, (c.funnel[i + 1].value / maxStage) * 100)
                      : widthPct;
                  const pctOfFirst = firstStage > 0 ? (stage.value / firstStage) * 100 : 0;
                  const isSelected = filters.funnelStage === stage.key;
                  const dropSeverity =
                    stage.drop_from_previous > 40 ? "text-critical" : stage.drop_from_previous > 15 ? "text-warning" : "text-muted-foreground";
                  return (
                    <li key={stage.key}>
                      <button
                        type="button"
                        onClick={() => toggleStage(stage.key)}
                        onMouseEnter={() => setHover(stage.key)}
                        onMouseLeave={() => setHover(null)}
                        aria-pressed={isSelected}
                        aria-label={`Filtrar por etapa ${stage.stage}`}
                        className="w-full text-left"
                      >
                        <div className="flex items-baseline justify-between text-xs">
                          <span className={cn("font-medium", isSelected ? "text-primary" : "text-foreground")}>
                            {stage.stage}
                          </span>
                          <span className="tabular-nums text-muted-foreground">
                            {formatInt(stage.value)} · {pctOfFirst.toFixed(1)} %
                            {stage.drop_from_previous > 0 && (
                              <span className={cn("ml-2 font-semibold", dropSeverity)}>
                                −{formatPercent(stage.drop_from_previous)}
                              </span>
                            )}
                          </span>
                        </div>
                        {/* Segmento trapezoidal: clip-path angula los bordes laterales según la etapa siguiente */}
                        <div className="mt-1 flex justify-center">
                          <div
                            className={cn(
                              "h-8 rounded-sm transition-all",
                              isSelected
                                ? "bg-primary"
                                : hover === stage.key
                                  ? "bg-primary/70"
                                  : "bg-primary/40",
                            )}
                            style={{
                              width: `${widthPct}%`,
                              clipPath: `polygon(0% 0%, 100% 0%, ${50 + nextWidthPct / 2}% 100%, ${50 - nextWidthPct / 2}% 100%)`,
                            }}
                          />
                        </div>
                      </button>
                    </li>
                  );
                })}
              </ul>

              {activeStage && (
                <div className="rounded-md border border-primary/30 bg-primary/5 p-3 text-xs text-foreground">
                  <p className="font-semibold">Detalle: {activeStage.stage}</p>
                  <ul className="mt-1.5 space-y-1 text-muted-foreground">
                    <li>Usuarios en esta etapa: {formatInt(activeStage.value)}</li>
                    <li>
                      Carritos abandonados relacionados:{" "}
                      {formatInt(Math.round(c.funnel.find((f) => f.key === "add_to_cart")?.value ?? 0) -
                        Math.round(c.funnel.find((f) => f.key === "checkout")?.value ?? 0))}
                    </li>
                    <li>
                      Pagos fallidos en el escenario:{" "}
                      {formatInt(
                        snapshot?.events_by_type.find((e) => e.event_type === "PAYMENT_FAILED")?.count ?? 0,
                      )}
                    </li>
                    <li>Caída respecto a la etapa anterior: {formatPercent(activeStage.drop_from_previous)}</li>
                  </ul>
                  <Badge variant="outline" className="mt-2 text-[10px]">
                    Filtro aplicado a todo el dashboard
                  </Badge>
                </div>
              )}
            </div>

            {/* Evolución temporal de la conversión con banda de promedio */}
            <ConversionHistoryChart data={c.history} />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {insights.map((insight) => (
              <InsightCard key={insight.id} insight={insight} />
            ))}
          </div>
        </div>
      )}
    </Panel>
  );
}

function ConversionHistoryChart({ data }: { data: { t: string; value: number }[] }) {
  if (!data.length) return <ChartSkeleton height={260} />;
  const avg = data.reduce((a, b) => a + b.value, 0) / data.length;
  return (
    <div className="h-[280px] w-full">
      <div className="mb-1 flex items-center gap-1.5 text-xs text-muted-foreground">
        <TrendingDown className="h-3.5 w-3.5" aria-hidden />
        Evolución de la conversión (línea) con banda de promedio de la ventana
      </div>
      <ResponsiveContainer width="100%" height="90%">
        <ComposedChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
          <defs>
            <linearGradient id="conv-avg-band" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--color-info)" stopOpacity={0.12} />
              <stop offset="100%" stopColor="var(--color-info)" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
          <XAxis
            dataKey="t"
            tickFormatter={(t) => formatTime(t).slice(0, 5)}
            tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }}
            axisLine={false}
            tickLine={false}
            minTickGap={32}
          />
          <YAxis
            tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }}
            axisLine={false}
            tickLine={false}
            width={44}
            unit=" %"
          />
          <RTooltip
            contentStyle={CHART_TOOLTIP_STYLE}
            labelFormatter={(t) => formatTime(String(t))}
            formatter={(v: number) => [formatPercent(v), "Conversión"]}
          />
          <ReferenceLine y={avg} stroke="var(--color-info)" strokeDasharray="4 4" strokeWidth={1.5} />
          <Area type="monotone" dataKey="value" stroke="none" fill="url(#conv-avg-band)" isAnimationActive={false} />
          <Line type="monotone" dataKey="value" stroke="var(--color-success)" strokeWidth={2} dot={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function Stat({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="rounded-md border border-panel-border bg-muted/30 px-3 py-2">
      <p className="text-[11px] text-muted-foreground">{label}</p>
      <p className={`text-base font-semibold tabular-nums ${highlight ? "text-success" : "text-foreground"}`}>
        {value}
      </p>
    </div>
  );
}
