import { useMemo, useState } from "react";
import { Check, CheckCheck, Search } from "lucide-react";
import { Panel } from "@/components/common/Panel";
import { EmptyState, PanelSkeleton } from "@/components/common/States";
import { ALERT_STYLE } from "@/components/common/StatusIndicators";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useRealtimeDashboard } from "@/hooks/useRealtimeDashboard";
import { relativeTime, formatTime } from "@/utils/format";
import { cn } from "@/lib/utils";
import type { Alert, AlertLevel, AlertStatus } from "@/types";

const LEVELS: AlertLevel[] = ["CRITICAL", "WARNING", "INFO"];
const STATUS_FILTERS: Array<AlertStatus | "TODAS"> = ["TODAS", "ACTIVA", "RECONOCIDA", "RESUELTA"];

/** Indicador 10: alertas en tiempo real, agrupadas por severidad y componente. */
export function AlertsPanel({
  maxHeight = 480,
  limit,
}: {
  /** Alto máximo del listado con scroll interno. */
  maxHeight?: number;
  /** Límite de tarjetas visibles antes de "ver más" (modo resumen del dashboard). */
  limit?: number;
}) {
  const { snapshot, loading, filters, setFilters, acknowledgeAlert, resolveAlert } =
    useRealtimeDashboard();
  const [statusFilter, setStatusFilter] = useState<AlertStatus | "TODAS">("TODAS");
  const [query, setQuery] = useState("");
  const [visible, setVisible] = useState(limit ?? 8);

  const allAlerts = useMemo(() => snapshot?.alerts ?? [], [snapshot?.alerts]);

  // Conteo por severidad para las tarjetas superiores (siempre sobre el total, no el filtrado).
  const countsByLevel = useMemo(() => {
    const counts: Record<AlertLevel, number> = { CRITICAL: 0, WARNING: 0, INFO: 0 };
    allAlerts.forEach((a) => {
      if (a.status === "ACTIVA") counts[a.level] += 1;
    });
    return counts;
  }, [allAlerts]);

  const filtered = useMemo(() => {
    return allAlerts
      .filter((a) => filters.alertLevel === "TODOS" || a.level === filters.alertLevel)
      .filter((a) => statusFilter === "TODAS" || a.status === statusFilter)
      .filter(
        (a) =>
          !query ||
          a.title.toLowerCase().includes(query.toLowerCase()) ||
          a.component.toLowerCase().includes(query.toLowerCase()),
      )
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  }, [allAlerts, filters.alertLevel, statusFilter, query]);

  const grouped = useMemo(() => {
    const map = new Map<string, Alert[]>();
    filtered.slice(0, limit ? visible : visible).forEach((a) => {
      const list = map.get(a.component) ?? [];
      list.push(a);
      map.set(a.component, list);
    });
    return [...map.entries()];
  }, [filtered, visible, limit]);

  const activeCount = allAlerts.filter((a) => a.status === "ACTIVA").length;

  // Ventana de tiempo para posicionar la mini línea temporal.
  const timeline = useMemo(() => {
    if (allAlerts.length === 0) return { points: [], min: 0, max: 1 };
    const times = allAlerts.map((a) => new Date(a.timestamp).getTime());
    const min = Math.min(...times);
    const max = Math.max(...times);
    return { points: allAlerts, min, max: max === min ? min + 1 : max };
  }, [allAlerts]);

  const toggleLevel = (level: AlertLevel) => {
    setFilters({ alertLevel: filters.alertLevel === level ? "TODOS" : level });
  };

  return (
    <Panel
      title="Alertas en tiempo real"
      description={`${activeCount} alertas activas en el escenario ${snapshot?.scenario ?? ""}`}
      tooltip="Alertas emitidas por los jobs de Flink y por el monitoreo de infraestructura del backend consumidor."
      actions={
        !limit && (
          <div className="flex flex-wrap items-center gap-1">
            {STATUS_FILTERS.map((s) => (
              <Button
                key={s}
                size="sm"
                variant={statusFilter === s ? "secondary" : "ghost"}
                className="h-7 px-2 text-xs"
                onClick={() => setStatusFilter(s)}
              >
                {s === "TODAS" ? "Todos los estados" : s}
              </Button>
            ))}
            <div className="relative">
              <Search
                className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
                aria-hidden
              />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Buscar alerta"
                aria-label="Buscar alertas"
                className="h-7 w-40 pl-7 text-xs"
              />
            </div>
          </div>
        )
      }
    >
      {loading ? (
        <PanelSkeleton rows={5} />
      ) : (
        <div className="space-y-4">
          {/* (a) Tarjetas por severidad con filtro cruzado */}
          {allAlerts.length > 0 && (
            <div className="grid grid-cols-3 gap-2">
              {LEVELS.map((level) => {
                const active = filters.alertLevel === level;
                const style = ALERT_STYLE[level];
                return (
                  <button
                    key={level}
                    type="button"
                    onClick={() => toggleLevel(level)}
                    aria-pressed={active}
                    aria-label={`Filtrar alertas ${style.label}, ${countsByLevel[level]} activas`}
                    className={cn(
                      "rounded-md border border-l-2 bg-muted/25 px-3 py-2 text-left transition-colors hover:bg-muted/40",
                      style.border,
                      active && "ring-1 ring-primary border-primary/60",
                    )}
                  >
                    <p className="text-[11px] font-medium text-muted-foreground">{style.label}</p>
                    <p className="mt-0.5 text-xl font-semibold tabular-nums text-foreground">
                      {countsByLevel[level]}
                    </p>
                  </button>
                );
              })}
            </div>
          )}

          {/* (b) Mini línea de tiempo horizontal */}
          {timeline.points.length > 0 && !limit && (
            <div className="relative h-8 rounded-md border border-panel-border bg-muted/20">
              {timeline.points.map((a) => {
                const t = new Date(a.timestamp).getTime();
                const pct = ((t - timeline.min) / (timeline.max - timeline.min)) * 100;
                return (
                  <Tooltip key={a.id}>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        className={cn(
                          "absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border border-panel-border",
                          a.level === "CRITICAL" && "bg-critical",
                          a.level === "WARNING" && "bg-warning",
                          a.level === "INFO" && "bg-info",
                        )}
                        style={{ left: `${pct}%` }}
                        aria-label={`${a.title} · ${formatTime(a.timestamp)}`}
                      />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs text-xs">
                      <p className="font-medium">{a.title}</p>
                      <p className="text-muted-foreground">
                        {a.component} · {formatTime(a.timestamp)}
                      </p>
                    </TooltipContent>
                  </Tooltip>
                );
              })}
            </div>
          )}

          {/* (c) Lista agrupada por componente */}
          {allAlerts.length === 0 ? (
            <EmptyState
              title="Sin alertas registradas"
              description="El escenario actual no emitió advertencias ni eventos críticos."
            />
          ) : filtered.length === 0 ? (
            <EmptyState
              title="Sin alertas para el filtro seleccionado"
              description="Ajusta la severidad, el estado o la búsqueda indicada."
            />
          ) : (
            <div className="space-y-4 overflow-y-auto pr-1" style={{ maxHeight }}>
              {grouped.map(([component, alerts]) => (
                <div key={component}>
                  <h3 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                    {component} · {alerts.length}
                  </h3>
                  <ul className="space-y-2">
                    {alerts.map((a) => (
                      <li
                        key={a.id}
                        className={cn(
                          "rounded-md border border-panel-border border-l-2 bg-muted/25 p-3",
                          ALERT_STYLE[a.level].border,
                          a.status === "RESUELTA" && "opacity-60",
                        )}
                      >
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div className="min-w-0">
                            <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-foreground">
                              {a.title}
                              <Badge
                                variant="outline"
                                className={cn("text-[10px]", ALERT_STYLE[a.level].badge)}
                              >
                                {ALERT_STYLE[a.level].label}
                              </Badge>
                              <Badge variant="secondary" className="text-[10px]">
                                {a.status}
                              </Badge>
                            </p>
                            <p className="mt-1 text-xs text-muted-foreground">{a.description}</p>
                            <p className="mt-1 text-[11px] text-muted-foreground">
                              {relativeTime(a.timestamp)} ({formatTime(a.timestamp)})
                            </p>
                          </div>
                          {!limit && (
                            <div className="flex shrink-0 gap-1">
                              <Button
                                size="sm"
                                variant="ghost"
                                className="h-7 px-2 text-xs"
                                disabled={a.status !== "ACTIVA"}
                                onClick={() => acknowledgeAlert(a.id)}
                              >
                                <Check className="mr-1 h-3.5 w-3.5" aria-hidden /> Reconocer
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                className="h-7 px-2 text-xs"
                                disabled={a.status === "RESUELTA"}
                                onClick={() => resolveAlert(a.id)}
                              >
                                <CheckCheck className="mr-1 h-3.5 w-3.5" aria-hidden /> Resolver
                              </Button>
                            </div>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
              {filtered.length > visible && (
                <Button
                  size="sm"
                  variant="outline"
                  className="w-full text-xs"
                  onClick={() => setVisible((v) => v + 8)}
                >
                  Ver más ({filtered.length - visible} restantes)
                </Button>
              )}
            </div>
          )}
        </div>
      )}
    </Panel>
  );
}
