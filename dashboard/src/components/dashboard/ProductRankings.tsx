/**
 * Rankings visuales de productos: barras de progreso, avatar de categoría,
 * métricas tabulares y filtrado cruzado por producto seleccionado.
 */
import { useMemo, useState } from "react";
import { Panel } from "@/components/common/Panel";
import { PanelSkeleton } from "@/components/common/States";
import { DeltaBadge } from "@/components/common/StatusIndicators";
import { Button } from "@/components/ui/button";
import { useRealtimeDashboard } from "@/hooks/useRealtimeDashboard";
import type { ProductMetric } from "@/types";
import { formatCompactCurrency, formatInt, formatRatioAsPercent } from "@/utils/format";
import { seriesColor } from "@/lib/palette";
import { cn } from "@/lib/utils";

const TOPS = [5, 10, 20] as const;

/** Avatar circular con la inicial de la categoría, color determinístico. */
function CategoryAvatar({ category }: { category: string }) {
  const idx = Math.abs([...category].reduce((a, c) => a + c.charCodeAt(0), 0)) % 6;
  const color = seriesColor(idx);
  return (
    <span
      className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold text-primary-foreground"
      style={{ backgroundColor: color }}
      aria-hidden
    >
      {category.charAt(0).toUpperCase()}
    </span>
  );
}

/** Fila genérica de ranking con barra proporcional y filtrado cruzado. */
function RankingRow({
  rank,
  product,
  value,
  valueLabel,
  max,
  secondary,
  selected,
  dimmed,
  onSelect,
}: {
  rank: number;
  product: ProductMetric;
  value: number;
  valueLabel: string;
  max: number;
  secondary: string;
  selected: boolean;
  dimmed: boolean;
  onSelect: () => void;
}) {
  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        aria-pressed={selected}
        aria-label={`Filtrar por ${product.name}`}
        className={cn(
          "flex w-full items-center gap-3 rounded-md px-2 py-1.5 text-left transition-all hover:bg-muted/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring",
          selected && "bg-primary/8 ring-1 ring-primary/40",
          dimmed && "opacity-40",
        )}
      >
        <span className="w-5 shrink-0 text-xs font-semibold tabular-nums text-muted-foreground">
          {rank}
        </span>
        <CategoryAvatar category={product.category} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-foreground">{product.name}</p>
          <p className="truncate text-[11px] text-muted-foreground">{secondary}</p>
          <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-info transition-all"
              style={{ width: `${max > 0 ? (value / max) * 100 : 0}%` }}
            />
          </div>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-sm font-semibold tabular-nums text-foreground">{valueLabel}</p>
          <DeltaBadge value={product.change} />
        </div>
      </button>
    </li>
  );
}

/** Indicador 5: productos más visitados. */
export function TopViewedProducts() {
  const { snapshot, loading, filters, setFilters } = useRealtimeDashboard();
  const [top, setTop] = useState<number>(5);
  const items = snapshot?.top_viewed_products.slice(0, top) ?? [];
  const max = Math.max(1, ...items.map((p) => p.views));

  const toggle = (id: string) => setFilters({ product: filters.product === id ? "TODOS" : id });

  return (
    <Panel
      title="Productos más visitados"
      description="Ranking por eventos VIEW_PRODUCT y permanencia promedio"
      tooltip="El tiempo de permanencia se estima con la diferencia entre eventos consecutivos de la misma sesión."
      actions={
        <div className="flex gap-1" role="group" aria-label="Cantidad de productos">
          {TOPS.map((t) => (
            <Button
              key={t}
              size="sm"
              variant={top === t ? "secondary" : "ghost"}
              className="h-7 px-2 text-xs"
              onClick={() => setTop(t)}
            >
              Top {t}
            </Button>
          ))}
        </div>
      }
    >
      {loading ? (
        <PanelSkeleton rows={5} />
      ) : (
        <ol className="space-y-1">
          {items.map((p, i) => (
            <RankingRow
              key={p.id}
              rank={i + 1}
              product={p}
              value={p.views}
              valueLabel={formatInt(p.views)}
              max={max}
              secondary={`${p.category} · ${p.avg_dwell_seconds.toFixed(1)} s de permanencia`}
              selected={filters.product === p.id}
              dimmed={filters.product !== "TODOS" && filters.product !== p.id}
              onSelect={() => toggle(p.id)}
            />
          ))}
        </ol>
      )}
    </Panel>
  );
}

type SortKey = "units" | "orders" | "revenue" | "views";
const SORTS: Array<{ key: SortKey; label: string }> = [
  { key: "views", label: "Visitas" },
  { key: "units", label: "Unidades" },
  { key: "orders", label: "Órdenes" },
  { key: "revenue", label: "Ingresos" },
];

/** Indicador 6: productos más comprados. */
export function TopPurchasedProducts() {
  const { snapshot, loading, filters, setFilters } = useRealtimeDashboard();
  const [sort, setSort] = useState<SortKey>("units");
  const items = useMemo(
    () => [...(snapshot?.top_purchased_products ?? [])].sort((a, b) => b[sort] - a[sort]).slice(0, 10),
    [snapshot, sort],
  );
  const max = Math.max(1, ...items.map((p) => p[sort]));

  const toggle = (id: string) => setFilters({ product: filters.product === id ? "TODOS" : id });

  const valueLabel = (p: ProductMetric) => {
    if (sort === "revenue") return formatCompactCurrency(p.revenue);
    if (sort === "units") return formatInt(p.units);
    if (sort === "orders") return formatInt(p.orders);
    return formatInt(p.views);
  };

  return (
    <Panel
      title="Productos más comprados"
      description="Ranking por eventos PURCHASE consolidados por Flink"
      tooltip="Las órdenes agrupan varias unidades del mismo producto dentro de una misma compra."
      actions={
        <div className="flex flex-wrap gap-1" role="group" aria-label="Ordenar productos comprados">
          {SORTS.map((s) => (
            <Button
              key={s.key}
              size="sm"
              variant={sort === s.key ? "secondary" : "ghost"}
              className="h-7 px-2 text-xs"
              onClick={() => setSort(s.key)}
            >
              {s.label}
            </Button>
          ))}
        </div>
      }
    >
      {loading ? (
        <PanelSkeleton rows={5} />
      ) : (
        <ol className="space-y-1">
          {items.map((p, i) => (
            <RankingRow
              key={p.id}
              rank={i + 1}
              product={p}
              value={p[sort]}
              valueLabel={valueLabel(p)}
              max={max}
              secondary={`${p.category} · ${formatInt(p.orders)} órdenes · conv. ${formatRatioAsPercent(
                p.views > 0 ? p.units / p.views : 0,
              )}`}
              selected={filters.product === p.id}
              dimmed={filters.product !== "TODOS" && filters.product !== p.id}
              onSelect={() => toggle(p.id)}
            />
          ))}
        </ol>
      )}
    </Panel>
  );
}
