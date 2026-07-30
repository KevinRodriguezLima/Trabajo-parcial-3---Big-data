import type { ReactNode } from "react";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Info as InfoIcon,
  Lightbulb,
  type LucideIcon,
} from "lucide-react";
import { Area, AreaChart, ResponsiveContainer } from "recharts";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { DeltaBadge } from "@/components/common/StatusIndicators";
import type { Insight, InsightTone } from "@/lib/analytics";

export type MetricTone = "positivo" | "neutral" | "critico" | "especial";

const TONE_TEXT: Record<MetricTone, string> = {
  positivo: "text-success",
  neutral: "text-info",
  critico: "text-critical",
  especial: "text-special",
};

const TONE_VAR: Record<MetricTone, string> = {
  positivo: "var(--color-success)",
  neutral: "var(--color-info)",
  critico: "var(--color-critical)",
  especial: "var(--color-special)",
};

const TONE_GLOW: Record<MetricTone, string> = {
  positivo: "from-success/12",
  neutral: "from-info/12",
  critico: "from-critical/14",
  especial: "from-special/12",
};

export interface MetricCardProps {
  label: string;
  value: string;
  delta?: number;
  inverseDelta?: boolean;
  spark?: number[];
  icon?: LucideIcon;
  tone?: MetricTone;
  tooltip?: string;
  context?: string;
  onClick?: () => void;
  active?: boolean;
  className?: string;
}

/** Nivel 1: métrica ejecutiva de gran tamaño con sparkline y contexto. */
export function HeroMetricCard({
  label,
  value,
  delta,
  inverseDelta,
  spark = [],
  icon: Icon,
  tone = "neutral",
  tooltip,
  context,
  onClick,
  active,
  className,
}: MetricCardProps) {
  const body = (
    <article
      className={cn(
        "panel group relative overflow-hidden p-4 text-left transition-all",
        onClick && "cursor-pointer hover:border-primary/50",
        active && "border-primary ring-1 ring-primary/40",
        className,
      )}
      tabIndex={0}
      role={onClick ? "button" : undefined}
      onClick={onClick}
      onKeyDown={(e) => {
        if (onClick && (e.key === "Enter" || e.key === " ")) {
          e.preventDefault();
          onClick();
        }
      }}
      aria-label={`${label}: ${value}`}
    >
      <div
        className={cn(
          "pointer-events-none absolute inset-x-0 top-0 h-24 bg-gradient-to-b to-transparent opacity-70",
          TONE_GLOW[tone],
        )}
        aria-hidden
      />
      <div className="relative flex items-start justify-between gap-2">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
        {Icon && <Icon className={cn("h-4 w-4 shrink-0", TONE_TEXT[tone])} aria-hidden />}
      </div>
      <p className="relative mt-2 truncate text-[28px] font-semibold leading-none tabular-nums text-foreground">
        {value}
      </p>
      <div className="relative mt-2 flex items-end justify-between gap-3">
        <div className="min-w-0">
          {typeof delta === "number" && <DeltaBadge value={delta} inverse={inverseDelta} />}
          {context && <p className="mt-1 truncate text-[11px] text-muted-foreground">{context}</p>}
        </div>
        <div className="h-10 w-24 shrink-0">
          <Sparkline data={spark} color={TONE_VAR[tone]} />
        </div>
      </div>
    </article>
  );
  if (!tooltip) return body;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{body}</TooltipTrigger>
      <TooltipContent className="max-w-xs">{tooltip}</TooltipContent>
    </Tooltip>
  );
}

/** Nivel 2: métrica compacta de apoyo. */
export function CompactMetricCard({
  label,
  value,
  delta,
  inverseDelta,
  spark = [],
  tone = "neutral",
  tooltip,
  onClick,
  active,
  className,
}: MetricCardProps) {
  const body = (
    <article
      className={cn(
        "panel flex items-center justify-between gap-3 px-3.5 py-3 transition-colors",
        onClick && "cursor-pointer hover:border-primary/50",
        active && "border-primary ring-1 ring-primary/40",
        className,
      )}
      tabIndex={0}
      onClick={onClick}
      aria-label={`${label}: ${value}`}
    >
      <div className="min-w-0">
        <p className="truncate text-[11px] font-medium text-muted-foreground">{label}</p>
        <p className="mt-0.5 truncate text-lg font-semibold tabular-nums text-foreground">{value}</p>
        {typeof delta === "number" && <DeltaBadge value={delta} inverse={inverseDelta} />}
      </div>
      <div className="h-8 w-16 shrink-0">
        <Sparkline data={spark} color={TONE_VAR[tone]} />
      </div>
    </article>
  );
  if (!tooltip) return body;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{body}</TooltipTrigger>
      <TooltipContent className="max-w-xs">{tooltip}</TooltipContent>
    </Tooltip>
  );
}

export function Sparkline({ data, color }: { data: number[]; color: string }) {
  if (!data.length) return null;
  const points = data.map((value, i) => ({ i, value }));
  const id = `spark-${color.replace(/[^a-z]/gi, "")}`;
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={points} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.35} />
            <stop offset="100%" stopColor={color} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <Area
          type="monotone"
          dataKey="value"
          stroke={color}
          fill={`url(#${id})`}
          strokeWidth={1.6}
          isAnimationActive={false}
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

const INSIGHT_META: Record<InsightTone, { icon: LucideIcon; text: string; ring: string }> = {
  positivo: { icon: CheckCircle2, text: "text-success", ring: "border-success/30 bg-success/8" },
  neutral: { icon: InfoIcon, text: "text-info", ring: "border-info/30 bg-info/8" },
  advertencia: { icon: AlertTriangle, text: "text-warning", ring: "border-warning/35 bg-warning/8" },
  critico: { icon: AlertTriangle, text: "text-critical", ring: "border-critical/40 bg-critical/8" },
};

/** Tarjeta de insight automático generado por reglas. */
export function InsightCard({
  insight,
  onAction,
  actionLabel,
}: {
  insight: Insight;
  onAction?: () => void;
  actionLabel?: string;
}) {
  const meta = INSIGHT_META[insight.tone];
  const Icon = meta.icon;
  return (
    <article className={cn("rounded-lg border p-3", meta.ring)}>
      <div className="flex items-start gap-2.5">
        <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", meta.text)} aria-hidden />
        <div className="min-w-0">
          <p className="text-sm font-medium leading-snug text-foreground">{insight.title}</p>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{insight.detail}</p>
          {onAction && (
            <button
              type="button"
              onClick={onAction}
              className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
            >
              {actionLabel ?? "Ver detalle"}
              <ArrowRight className="h-3 w-3" aria-hidden />
            </button>
          )}
        </div>
      </div>
    </article>
  );
}

/** Banner narrativo con el resumen automático del estado del sistema. */
export function SummaryBanner({ text, children }: { text: string; children?: ReactNode }) {
  return (
    <section
      className="panel flex flex-wrap items-start gap-3 border-l-2 border-l-primary p-4"
      aria-label="Resumen automático del sistema"
    >
      <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden />
      <p className="min-w-[240px] flex-1 text-sm leading-relaxed text-foreground/90">{text}</p>
      {children}
    </section>
  );
}