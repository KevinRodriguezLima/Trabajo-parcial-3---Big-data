import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Panel } from "@/components/common/Panel";
import { ChartSkeleton, EmptyState } from "@/components/common/States";
import { useRealtimeDashboard } from "@/hooks/useRealtimeDashboard";
import { formatInt } from "@/utils/format";
import { CATEGORY_COLOR, CATEGORY_LABEL, CHART_TOOLTIP_STYLE } from "@/lib/palette";
import { cn } from "@/lib/utils";
import type { EventCategory } from "@/types";

const CATEGORIES: EventCategory[] = ["DIGITAL", "COMPRAS", "IOT", "SISTEMA"];

/** Indicador 3: eventos por tipo, agrupados por categoría con chips resumen. */
export function EventsByTypeChart() {
  const { snapshot, loading, filters, setFilters } = useRealtimeDashboard();

  const grouped = useMemo(() => {
    if (!snapshot) return [];
    const total = snapshot.events_by_type.reduce((a, b) => a + b.count, 0) || 1;
    return CATEGORIES.map((category) => {
      const items = snapshot.events_by_type
        .filter((e) => e.category === category)
        .sort((a, b) => b.count - a.count);
      const catTotal = items.reduce((a, b) => a + b.count, 0);
      return { category, items, catTotal, share: (catTotal / total) * 100 };
    });
  }, [snapshot]);

  const flatData = useMemo(
    () =>
      grouped.flatMap((g) =>
        g.items.map((it) => ({ ...it, catShare: g.share, groupLabel: CATEGORY_LABEL[g.category] })),
      ),
    [grouped],
  );

  const toggleType = (type: string) => {
    setFilters({ eventType: filters.eventType === type ? "TODOS" : (type as never) });
  };

  return (
    <Panel
      title="Eventos por tipo"
      description="Distribución acumulada por tipo de evento, agrupada por categoría"
      tooltip="Conteo acumulado por event_type desde el inicio de la ejecución del escenario. Haz clic en una barra para filtrar el resto del dashboard por ese tipo de evento."
      actions={
        <div className="flex flex-wrap gap-2" role="group" aria-label="Resumen por categoría">
          {grouped.map((g) => (
            <span
              key={g.category}
              className="flex items-center gap-1.5 rounded-full border border-panel-border px-2.5 py-1 text-[11px] text-muted-foreground"
            >
              <span className="h-2 w-2 rounded-sm" style={{ background: CATEGORY_COLOR[g.category] }} aria-hidden />
              {CATEGORY_LABEL[g.category]} · {g.share.toFixed(1)} %
            </span>
          ))}
        </div>
      }
    >
      {loading ? (
        <ChartSkeleton height={420} />
      ) : flatData.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="h-[420px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={flatData} layout="vertical" margin={{ top: 4, right: 32, left: 8, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
              <XAxis
                type="number"
                tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey="event_type"
                width={140}
                tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }}
                axisLine={false}
                tickLine={false}
              />
              <RTooltip
                cursor={{ fill: "var(--color-muted)", opacity: 0.35 }}
                contentStyle={CHART_TOOLTIP_STYLE}
                formatter={(value: number, _n, item) => [
                  `${formatInt(value)} eventos (${item.payload.percentage.toFixed(2)} % del total, ${item.payload.catShare.toFixed(1)} % de su categoría "${item.payload.groupLabel}")`,
                  item.payload.event_type,
                ]}
              />
              <Bar
                dataKey="count"
                radius={[0, 4, 4, 0]}
                animationDuration={400}
                onClick={(d: { event_type?: string }) => d?.event_type && toggleType(d.event_type)}
                cursor="pointer"
              >
                {flatData.map((d) => {
                  const active = filters.eventType === d.event_type;
                  const dimmed = filters.eventType !== "TODOS" && !active;
                  return (
                    <Cell
                      key={d.event_type}
                      fill={CATEGORY_COLOR[d.category]}
                      opacity={dimmed ? 0.35 : 1}
                      className={cn(active && "drop-shadow-[0_0_4px_var(--color-primary)]")}
                    />
                  );
                })}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Panel>
  );
}
