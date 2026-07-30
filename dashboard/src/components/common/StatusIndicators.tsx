import { cn } from "@/lib/utils";
import type { AlertLevel, ComponentStatus, ConnectionStatus } from "@/types";

const CONNECTION_STYLE: Record<ConnectionStatus, { label: string; dot: string; text: string }> = {
  CONECTADO: { label: "Conectado", dot: "bg-success", text: "text-success" },
  RECONECTANDO: { label: "Reconectando", dot: "bg-warning animate-pulse", text: "text-warning" },
  DESCONECTADO: { label: "Desconectado", dot: "bg-critical", text: "text-critical" },
  DEMO: { label: "Modo demostración", dot: "bg-info animate-pulse", text: "text-info" },
};

export function ConnectionBadge({ status }: { status: ConnectionStatus }) {
  const s = CONNECTION_STYLE[status];
  return (
    <span
      className="inline-flex items-center gap-2 rounded-md border border-panel-border bg-muted/40 px-2.5 py-1 text-xs font-medium"
      role="status"
      aria-live="polite"
    >
      <span className={cn("h-2 w-2 rounded-full", s.dot)} aria-hidden />
      <span className={s.text}>{s.label}</span>
    </span>
  );
}

const COMPONENT_STYLE: Record<ComponentStatus, { dot: string; text: string; label: string }> = {
  OPERATIVO: { dot: "bg-success", text: "text-success", label: "Operativo" },
  DEGRADADO: { dot: "bg-warning", text: "text-warning", label: "Degradado" },
  DESCONECTADO: { dot: "bg-critical", text: "text-critical", label: "Desconectado" },
};

export function ComponentStatusBadge({ status }: { status: ComponentStatus }) {
  const s = COMPONENT_STYLE[status];
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-xs font-medium", s.text)}>
      <span className={cn("h-2 w-2 rounded-full", s.dot)} aria-hidden />
      {s.label}
    </span>
  );
}

export const ALERT_STYLE: Record<AlertLevel, { label: string; badge: string; border: string }> = {
  INFO: {
    label: "Informativa",
    badge: "bg-info/15 text-info border-info/30",
    border: "border-l-info",
  },
  WARNING: {
    label: "Advertencia",
    badge: "bg-warning/15 text-warning border-warning/30",
    border: "border-l-warning",
  },
  CRITICAL: {
    label: "Crítica",
    badge: "bg-critical/15 text-critical border-critical/40",
    border: "border-l-critical",
  },
};

export function DeltaBadge({ value, inverse = false }: { value: number; inverse?: boolean }) {
  const positive = inverse ? value < 0 : value > 0;
  const neutral = Math.abs(value) < 0.05;
  const cls = neutral
    ? "text-muted-foreground"
    : positive
      ? "text-success"
      : "text-critical";
  const sign = value > 0 ? "+" : "";
  return (
    <span className={cn("text-xs font-medium tabular-nums", cls)}>
      {sign}
      {value.toFixed(1)} %
    </span>
  );
}