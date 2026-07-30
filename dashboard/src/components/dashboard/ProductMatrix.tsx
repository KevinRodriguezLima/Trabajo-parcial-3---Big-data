/**
 * Matriz de desempeño de productos: visitas (X) vs conversión (Y),
 * tamaño = ingresos. Cuadrantes calculados con buildProductMatrix.
 */
import { useMemo } from "react";
import {
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { Panel } from "@/components/common/Panel";
import { ChartSkeleton, EmptyState } from "@/components/common/States";
import { useRealtimeDashboard } from "@/hooks/useRealtimeDashboard";
import { buildProductMatrix, QUADRANT_META, type ProductPoint, type Quadrant } from "@/lib/analytics";
import { CHART_TOOLTIP_STYLE } from "@/lib/palette";
import { formatCompactCurrency, formatInt, formatRatioAsPercent } from "@/utils/format";
import { cn } from "@/lib/utils";

const QUADRANT_ORDER: Quadrant[] = ["estrella", "fuga", "oculto", "bajo"];

function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: ProductPoint }> }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div style={CHART_TOOLTIP_STYLE} className="min-w-[180px] p-2.5">
      <p className="text-xs font-semibold text-foreground">{p.name}</p>
      <p className="text-[11px] text-muted-foreground">{p.category}</p>
      <dl className="mt-1.5 grid grid-cols-2 gap-x-2 gap-y-0.5 text-[11px]">
        <dt className="text-muted-foreground">Visitas</dt>
        <dd className="text-right tabular-nums text-foreground">{formatInt(p.views)}</dd>
        <dt className="text-muted-foreground">Unidades</dt>
        <dd className="text-right tabular-nums text-foreground">{formatInt(p.units)}</dd>
        <dt className="text-muted-foreground">Ingresos</dt>
        <dd className="text-right tabular-nums text-foreground">{formatCompactCurrency(p.revenue)}</dd>
        <dt className="text-muted-foreground">Conversión</dt>
        <dd className="text-right tabular-nums text-foreground">{formatRatioAsPercent(p.conversion)}</dd>
      </dl>
    </div>
  );
}

/** Panel principal de productos: matriz visitas × conversión con cuadrantes. */
export function ProductMatrix() {
  const { snapshot, loading, filters, setFilters } = useRealtimeDashboard();
  const products = snapshot?.top_viewed_products ?? [];
  const { points, avgConversion, avgViews } = useMemo(() => buildProductMatrix(products), [products]);

  const byQuadrant = useMemo(() => {
    const map = new Map<Quadrant, ProductPoint[]>();
    QUADRANT_ORDER.forEach((q) => map.set(q, []));
    points.forEach((p) => map.get(p.quadrant)?.push(p));
    return map;
  }, [points]);

  const handleSelect = (id: string) => {
    setFilters({ product: filters.product === id ? "TODOS" : id });
  };

  return (
    <Panel
      level="primary"
      title="Matriz de desempeño de productos"
      description="Visitas vs. conversión; el tamaño del punto representa los ingresos generados"
      tooltip="Los cuadrantes se calculan comparando cada producto contra el promedio de visitas y conversión del catálogo visible."
    >
      {loading ? (
        <ChartSkeleton height={360} />
      ) : points.length === 0 ? (
        <EmptyState />
      ) : (
        <>
          <div className="h-[360px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 20, right: 24, bottom: 8, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis
                  type="number"
                  dataKey="views"
                  name="Visitas"
                  tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }}
                  axisLine={false}
                  tickLine={false}
                  label={{
                    value: "Visitas",
                    position: "insideBottom",
                    offset: -4,
                    fontSize: 11,
                    fill: "var(--color-muted-foreground)",
                  }}
                />
                <YAxis
                  type="number"
                  dataKey="conversion"
                  name="Conversión"
                  tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
                  tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }}
                  axisLine={false}
                  tickLine={false}
                  width={44}
                />
                <ZAxis type="number" dataKey="revenue" range={[60, 500]} name="Ingresos" />
                <ReferenceLine x={avgViews} stroke="var(--color-border)" strokeDasharray="4 4" />
                <ReferenceLine y={avgConversion} stroke="var(--color-border)" strokeDasharray="4 4" />
                <RTooltip content={<CustomTooltip />} cursor={{ strokeDasharray: "3 3" }} />
                {QUADRANT_ORDER.map((q) => (
                  <Scatter
                    key={q}
                    name={QUADRANT_META[q].label}
                    data={byQuadrant.get(q) ?? []}
                    onClick={(d: unknown) => handleSelect((d as ProductPoint).id)}
                    style={{ cursor: "pointer" }}
                  >
                    {(byQuadrant.get(q) ?? []).map((p) => {
                      const selected = filters.product === "TODOS" || filters.product === p.id;
                      return (
                        <Cell
                          key={p.id}
                          fill={QUADRANT_META[q].color}
                          fillOpacity={selected ? 0.85 : 0.18}
                          stroke={filters.product === p.id ? "var(--color-foreground)" : "none"}
                          strokeWidth={filters.product === p.id ? 1.5 : 0}
                        />
                      );
                    })}
                  </Scatter>
                ))}
              </ScatterChart>
            </ResponsiveContainer>
          </div>

          {/* Leyenda explicativa de cuadrantes */}
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {QUADRANT_ORDER.map((q) => (
              <div key={q} className="flex items-start gap-1.5 rounded-md border border-panel-border/60 p-2">
                <span
                  className="mt-1 h-2 w-2 shrink-0 rounded-full"
                  style={{ backgroundColor: QUADRANT_META[q].color }}
                  aria-hidden
                />
                <div className="min-w-0">
                  <p className="text-[11px] font-medium leading-tight text-foreground">
                    {QUADRANT_META[q].label}
                  </p>
                  <p className="text-[10px] leading-tight text-muted-foreground">
                    {QUADRANT_META[q].description}
                  </p>
                </div>
              </div>
            ))}
          </div>

          {/* Resumen textual por cuadrante */}
          <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
            {QUADRANT_ORDER.map((q) => {
              const items = byQuadrant.get(q) ?? [];
              const examples = items.slice(0, 3).map((p) => p.name).join(", ");
              return (
                <p key={q} className={cn("text-xs text-muted-foreground")}>
                  <span className="font-medium text-foreground">{QUADRANT_META[q].label}:</span>{" "}
                  {items.length} producto{items.length === 1 ? "" : "s"}
                  {examples ? ` (${examples}${items.length > 3 ? "…" : ""})` : ""}.
                </p>
              );
            })}
          </div>
        </>
      )}
    </Panel>
  );
}
