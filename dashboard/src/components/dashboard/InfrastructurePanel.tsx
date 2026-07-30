import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react";
import { Panel } from "@/components/common/Panel";
import { PanelSkeleton } from "@/components/common/States";
import { ComponentStatusBadge } from "@/components/common/StatusIndicators";
import { useRealtimeDashboard } from "@/hooks/useRealtimeDashboard";
import { formatInt, relativeTime } from "@/utils/format";
import { cn } from "@/lib/utils";
import type { ComponentStatus } from "@/types";

const FLOW = ["Agentes", "Kafka", "Flink", "Backend", "Dashboard"];

const DOT_BY_STATUS: Record<ComponentStatus, string> = {
  OPERATIVO: "bg-success",
  DEGRADADO: "bg-warning",
  DESCONECTADO: "bg-critical",
};

/** Panel de estado de la plataforma: tarjetas de salud + diagrama de flujo animado. */
export function InfrastructurePanel() {
  const { snapshot, loading } = useRealtimeDashboard();
  const components = snapshot?.infrastructure ?? [];
  const flowActive = components.length > 0 && components.every((c) => c.status !== "DESCONECTADO");
  const maxLatency = Math.max(1, ...components.map((c) => c.latency_ms));

  // Semáforo global: rojo si algún componente desconectado, ámbar si degradado, verde si todo operativo.
  const globalStatus: ComponentStatus = components.some((c) => c.status === "DESCONECTADO")
    ? "DESCONECTADO"
    : components.some((c) => c.status === "DEGRADADO")
      ? "DEGRADADO"
      : "OPERATIVO";
  const GlobalIcon = globalStatus === "OPERATIVO" ? CheckCircle2 : globalStatus === "DEGRADADO" ? AlertTriangle : XCircle;

  return (
    <Panel
      title="Estado de la plataforma"
      description="Salud de cada componente de la arquitectura orientada a eventos"
      tooltip="La latencia corresponde al tiempo entre event_timestamp e ingestion_timestamp medido por el backend consumidor."
      actions={
        !loading && (
          <span
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md border border-panel-border bg-muted/30 px-2.5 py-1 text-xs font-medium",
              globalStatus === "OPERATIVO" && "text-success",
              globalStatus === "DEGRADADO" && "text-warning",
              globalStatus === "DESCONECTADO" && "text-critical",
            )}
            role="status"
            aria-label={`Semáforo general: ${globalStatus}`}
          >
            <GlobalIcon className="h-3.5 w-3.5" aria-hidden />
            {globalStatus === "OPERATIVO"
              ? "Clúster saludable"
              : globalStatus === "DEGRADADO"
                ? "Rendimiento degradado"
                : "Componente desconectado"}
          </span>
        )
      }
    >
      {loading ? (
        <PanelSkeleton rows={6} />
      ) : (
        <>
          {/* Diagrama de flujo horizontal animado entre componentes de la arquitectura */}
          <div className="mb-4 flex flex-wrap items-center gap-2">
            {FLOW.map((node, i) => (
              <span key={node} className="flex items-center gap-2">
                <span className="rounded-md border border-panel-border bg-muted/40 px-2.5 py-1 text-xs font-medium">
                  {node}
                </span>
                {i < FLOW.length - 1 && (
                  <svg width="34" height="10" aria-hidden>
                    <line
                      x1="0"
                      y1="5"
                      x2="34"
                      y2="5"
                      stroke={flowActive ? "var(--color-success)" : "var(--color-critical)"}
                      strokeWidth="2"
                      className={flowActive ? "flow-dash" : undefined}
                    />
                  </svg>
                )}
              </span>
            ))}
          </div>

          {/* Tarjetas de salud por componente */}
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {components.map((c) => (
              <article
                key={c.id}
                className="rounded-md border border-panel-border bg-muted/20 p-3"
                aria-label={`Estado de ${c.name}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="truncate text-sm font-medium text-foreground">{c.name}</p>
                  <ComponentStatusBadge status={c.status} />
                </div>
                <p className="mt-1 text-[11px] text-muted-foreground">{c.responsibility}</p>

                <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <p className="text-muted-foreground">Latencia</p>
                    <p className="font-semibold tabular-nums text-foreground">{c.latency_ms} ms</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Mensajes</p>
                    <p className="font-semibold tabular-nums text-foreground">{formatInt(c.messages_processed)}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Errores</p>
                    <p className={cn("font-semibold tabular-nums", c.errors > 0 ? "text-critical" : "text-foreground")}>
                      {formatInt(c.errors)}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Heartbeat</p>
                    <p className="font-semibold text-foreground">{relativeTime(c.last_heartbeat)}</p>
                  </div>
                </div>

                {/* Micro barra de latencia relativa al componente más lento */}
                <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn("h-full rounded-full transition-all", DOT_BY_STATUS[c.status])}
                    style={{ width: `${(c.latency_ms / maxLatency) * 100}%` }}
                  />
                </div>
              </article>
            ))}
          </div>
        </>
      )}
    </Panel>
  );
}
