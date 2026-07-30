import { useMemo, useState } from "react";
import { ChevronRight, Users } from "lucide-react";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip as RTooltip,
  Treemap,
  XAxis,
  YAxis,
} from "recharts";
import { Panel } from "@/components/common/Panel";
import { PanelSkeleton } from "@/components/common/States";
import { DeltaBadge } from "@/components/common/StatusIndicators";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Sparkline } from "@/components/common/Cards";
import { useRealtimeDashboard } from "@/hooks/useRealtimeDashboard";
import { formatInt, formatPercent, formatTime } from "@/utils/format";
import type { AudienceMetric } from "@/types";
import { cn } from "@/lib/utils";

const PRIORITY_STYLE: Record<AudienceMetric["priority"], string> = {
  ALTA: "border-critical/40 bg-critical/10 text-critical",
  MEDIA: "border-warning/40 bg-warning/10 text-warning",
  BAJA: "border-info/40 bg-info/10 text-info",
};

const PRIORITY_VAR: Record<AudienceMetric["priority"], string> = {
  ALTA: "var(--color-critical)",
  MEDIA: "var(--color-warning)",
  BAJA: "var(--color-info)",
};

interface TreemapNode {
  id: string;
  name: string;
  label: string;
  size: number;
  percentage: number;
  priority: AudienceMetric["priority"];
}

interface TreemapCellProps extends Partial<TreemapNode> {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  selected?: string | null;
  onSelect?: (id: string) => void;
}

/** Nodo custom del treemap: color por prioridad y etiqueta nombre + %. */
function TreemapCell(props: TreemapCellProps) {
  const { x, y, width, height, id, label, percentage, priority, selected, onSelect } = props;
  if (
    x === undefined ||
    y === undefined ||
    width === undefined ||
    height === undefined ||
    !id ||
    !label ||
    percentage === undefined ||
    !priority ||
    !onSelect ||
    width < 2 ||
    height < 2
  ) {
    return null;
  }
  const isSelected = selected === id;
  const fill = PRIORITY_VAR[priority];
  const canShowText = width > 60 && height > 30;
  return (
    <g
      role="button"
      tabIndex={0}
      aria-label={`Filtrar por audiencia ${label}`}
      onClick={() => onSelect(id)}
      onKeyDown={(e: React.KeyboardEvent) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(id);
        }
      }}
      style={{ cursor: "pointer" }}
    >
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        fill={fill}
        fillOpacity={isSelected ? 0.85 : 0.45}
        stroke="var(--color-panel-border)"
        strokeWidth={isSelected ? 2 : 1}
      />
      {canShowText && (
        <>
          <text x={x + 8} y={y + 18} fontSize={11} fontWeight={600} fill="var(--color-foreground)">
            {label}
          </text>
          <text x={x + 8} y={y + 34} fontSize={10} fill="var(--color-foreground)" opacity={0.85}>
            {formatPercent(percentage)}
          </text>
        </>
      )}
    </g>
  );
}

/** Indicador 4: audiencias detectadas en tiempo real (treemap + tarjetas). */
export function AudiencePanel({ limit }: { limit?: number }) {
  const { snapshot, loading, filters, setFilters } = useRealtimeDashboard();
  const [selected, setSelected] = useState<AudienceMetric | null>(null);

  const audiences = useMemo(
    () => snapshot?.audiences.slice(0, limit ?? snapshot.audiences.length) ?? [],
    [limit, snapshot?.audiences],
  );
  const compact = typeof limit === "number";

  const treemapData: TreemapNode[] = useMemo(
    () =>
      audiences.map((a) => ({
        id: a.id,
        name: a.label,
        label: a.label,
        size: Math.max(1, a.users),
        percentage: a.percentage,
        priority: a.priority,
      })),
    [audiences],
  );

  const toggleAudience = (id: string) => {
    setFilters({ audience: filters.audience === id ? "TODAS" : id });
  };

  return (
    <>
      <Panel
        title="Audiencias detectadas en tiempo real"
        description="Segmentos calculados por el job de audiencias de Apache Flink"
        tooltip="Cada audiencia se detecta con reglas sobre ventanas deslizantes de eventos. Un usuario puede pertenecer a más de un segmento. El área del treemap es proporcional a la cantidad de usuarios."
      >
        {loading ? (
          <PanelSkeleton rows={6} />
        ) : (
          <div className="space-y-4">
            <div className={cn("w-full", compact ? "h-[160px]" : "h-[220px]")}>
              <ResponsiveContainer width="100%" height="100%">
                <Treemap
                  data={treemapData}
                  dataKey="size"
                  aspectRatio={4 / 3}
                  stroke="var(--color-panel-border)"
                  isAnimationActive={false}
                  content={<TreemapCell selected={filters.audience} onSelect={toggleAudience} />}
                />
              </ResponsiveContainer>
            </div>

            <ul
              className={cn(
                "grid gap-3",
                compact ? "sm:grid-cols-2" : "sm:grid-cols-2 xl:grid-cols-3",
              )}
            >
              {audiences.map((a) => {
                const isSelected = filters.audience === a.id;
                return (
                  <li key={a.id}>
                    <article
                      className={cn(
                        "flex h-full flex-col gap-2 rounded-lg border p-3 transition-colors",
                        isSelected
                          ? "border-primary bg-primary/5"
                          : "border-panel-border bg-muted/20 hover:border-primary/40",
                      )}
                    >
                      <button
                        type="button"
                        onClick={() => toggleAudience(a.id)}
                        className="flex items-start justify-between gap-2 text-left"
                        aria-pressed={isSelected}
                        aria-label={`Filtrar por audiencia ${a.label}`}
                      >
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-foreground">
                            {a.label}
                          </p>
                          <p className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground">
                            <Users className="h-3 w-3" aria-hidden />
                            {formatInt(a.users)} · {formatPercent(a.percentage)}
                          </p>
                        </div>
                        <Badge
                          variant="outline"
                          className={cn("shrink-0 text-[10px]", PRIORITY_STYLE[a.priority])}
                        >
                          {a.priority}
                        </Badge>
                      </button>

                      <div className="flex items-center justify-between">
                        <DeltaBadge value={a.change} />
                        <div className="h-8 w-20">
                          <Sparkline
                            data={a.history.map((h) => h.value)}
                            color={PRIORITY_VAR[a.priority]}
                          />
                        </div>
                      </div>

                      <div className="flex flex-wrap gap-1">
                        {a.rules.slice(0, 2).map((r) => (
                          <Badge
                            key={r}
                            variant="secondary"
                            className="max-w-full truncate text-[10px]"
                          >
                            {r}
                          </Badge>
                        ))}
                      </div>

                      <div className="flex flex-wrap gap-1">
                        {a.top_events.slice(0, 3).map((e) => (
                          <Badge key={e} variant="outline" className="text-[10px]">
                            {e}
                          </Badge>
                        ))}
                      </div>

                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="mt-auto justify-between text-xs"
                        onClick={() => setSelected(a)}
                        aria-label={`Ver detalle completo de ${a.label}`}
                      >
                        Ver detalle
                        <ChevronRight className="h-3.5 w-3.5" aria-hidden />
                      </Button>
                    </article>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </Panel>

      <Sheet open={!!selected} onOpenChange={(open) => !open && setSelected(null)}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-md">
          {selected && (
            <>
              <SheetHeader>
                <SheetTitle>{selected.label}</SheetTitle>
                <SheetDescription>{selected.description}</SheetDescription>
              </SheetHeader>
              <div className="space-y-5 px-4 pb-8 text-sm">
                <div className="grid grid-cols-2 gap-3">
                  <Metric label="Usuarios" value={formatInt(selected.users)} />
                  <Metric label="Porcentaje" value={formatPercent(selected.percentage)} />
                  <Metric label="Variación" value={`${selected.change.toFixed(1)} %`} />
                  <Metric label="Prioridad" value={selected.priority} />
                  {selected.avg_confidence !== undefined && (
                    <Metric
                      label="Confianza promedio"
                      value={formatPercent(selected.avg_confidence * 100)}
                    />
                  )}
                  {selected.recent_detections !== undefined && (
                    <Metric label="Detecciones" value={formatInt(selected.recent_detections)} />
                  )}
                </div>

                <Section title="Reglas de detección">
                  <ul className="list-inside list-disc space-y-1 text-xs text-muted-foreground">
                    {selected.rules.map((r) => (
                      <li key={r}>{r}</li>
                    ))}
                  </ul>
                </Section>

                <Section title="Eventos predominantes">
                  <div className="flex flex-wrap gap-1.5">
                    {selected.top_events.map((e) => (
                      <Badge key={e} variant="secondary" className="text-[10px]">
                        {e}
                      </Badge>
                    ))}
                  </div>
                </Section>

                <Section title="Productos más relacionados">
                  {selected.top_products.length > 0 ? (
                    <ul className="space-y-1 text-xs text-muted-foreground">
                      {selected.top_products.map((p) => (
                        <li key={p}>{p}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-xs text-muted-foreground">
                      Sin productos asociados en el snapshot actual.
                    </p>
                  )}
                </Section>

                <Section title="Regiones principales">
                  {selected.top_regions.length > 0 ? (
                    <div className="flex flex-wrap gap-1.5">
                      {selected.top_regions.map((r) => (
                        <Badge key={r} variant="outline" className="text-[10px]">
                          {r}
                        </Badge>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground">
                      Sin regiones asociadas en el snapshot actual.
                    </p>
                  )}
                </Section>

                {selected.sample_users && selected.sample_users.length > 0 && (
                  <Section title="Usuarios de ejemplo">
                    <div className="flex flex-wrap gap-1.5">
                      {selected.sample_users.map((user) => (
                        <Badge key={user} variant="outline" className="font-mono text-[10px]">
                          {user}
                        </Badge>
                      ))}
                    </div>
                  </Section>
                )}

                {selected.evidence && Object.keys(selected.evidence).length > 0 && (
                  <Section title="Evidencia de detección">
                    <dl className="grid grid-cols-2 gap-2 text-xs">
                      {Object.entries(selected.evidence).map(([key, value]) => (
                        <div
                          key={key}
                          className="rounded-md border border-panel-border bg-muted/20 px-2 py-1.5"
                        >
                          <dt className="truncate text-[10px] uppercase text-muted-foreground">
                            {key}
                          </dt>
                          <dd className="mt-0.5 font-medium text-foreground">
                            {formatEvidenceValue(value)}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </Section>
                )}

                <Section title="Evolución temporal">
                  <div className="h-[160px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart
                        data={selected.history}
                        margin={{ top: 4, right: 4, left: -20, bottom: 0 }}
                      >
                        <XAxis
                          dataKey="t"
                          tickFormatter={(t) => formatTime(t).slice(0, 5)}
                          tick={{ fontSize: 10, fill: "var(--color-muted-foreground)" }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          tick={{ fontSize: 10, fill: "var(--color-muted-foreground)" }}
                          axisLine={false}
                          tickLine={false}
                          width={40}
                        />
                        <RTooltip
                          contentStyle={{
                            background: "var(--color-popover)",
                            border: "1px solid var(--color-border)",
                            borderRadius: 8,
                            fontSize: 12,
                          }}
                          labelFormatter={(t) => formatTime(String(t))}
                          formatter={(v: number) => [`${formatInt(v)} usuarios`, "Audiencia"]}
                        />
                        <Area
                          type="monotone"
                          dataKey="value"
                          stroke="var(--color-special)"
                          fill="var(--color-special)"
                          fillOpacity={0.18}
                          strokeWidth={2}
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </Section>

                <Button variant="outline" className="w-full" onClick={() => setSelected(null)}>
                  Cerrar detalle
                </Button>
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-panel-border bg-muted/30 px-3 py-2">
      <p className="text-[11px] text-muted-foreground">{label}</p>
      <p className="text-sm font-semibold tabular-nums text-foreground">{value}</p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </h3>
      {children}
    </div>
  );
}

function formatEvidenceValue(value: unknown): string {
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "number") return formatInt(value);
  if (typeof value === "boolean") return value ? "Sí" : "No";
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}
