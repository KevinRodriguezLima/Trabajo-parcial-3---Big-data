import { Maximize2, Moon, MoreHorizontal, Pause, Play, RefreshCw, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useRealtimeDashboard } from "@/hooks/useRealtimeDashboard";
import { useTheme } from "@/hooks/useTheme";
import { SCENARIO_CONFIG } from "@/data/catalog";
import { formatTime } from "@/utils/format";
import { cn } from "@/lib/utils";
import type { TimeRange } from "@/types";
import type { ConnectionStatus } from "@/types";

const RANGES: Array<{ value: TimeRange; label: string }> = [
  { value: "5m", label: "5 min" },
  { value: "15m", label: "15 min" },
  { value: "1h", label: "1 hora" },
  { value: "all", label: "Todo" },
];

const STATUS_DOT: Record<ConnectionStatus, string> = {
  CONECTADO: "bg-success",
  RECONECTANDO: "bg-warning animate-pulse",
  DESCONECTADO: "bg-critical",
  DEMO: "bg-info animate-pulse",
};

const STATUS_LABEL: Record<ConnectionStatus, string> = {
  CONECTADO: "En vivo",
  RECONECTANDO: "Reconectando",
  DESCONECTADO: "Sin conexión",
  DEMO: "Simulación",
};

export function Topbar({ title, subtitle }: { title: string; subtitle?: string }) {
  const { status, paused, togglePause, refresh, lastUpdate, filters, setScenario, setFilters } =
    useRealtimeDashboard();
  const { theme, toggleTheme } = useTheme();

  const goFullscreen = () => {
    if (document.fullscreenElement) void document.exitFullscreen();
    else void document.documentElement.requestFullscreen();
  };

  return (
    <header className="no-print sticky top-0 z-20 border-b border-border bg-background/85 backdrop-blur">
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-4 py-2">
        <div className="min-w-0">
          <h1 className="truncate text-sm font-semibold tracking-tight text-foreground">{title}</h1>
          {subtitle && <p className="truncate text-[11px] text-muted-foreground">{subtitle}</p>}
        </div>

        <div className="flex items-center gap-2">
          {/* Estado de conexión unificado: origen, latencia de refresco y pausa. */}
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                onClick={togglePause}
                className={cn(
                  "hidden items-center gap-2 rounded-full border border-panel-border bg-muted/40 py-1 pl-2.5 pr-1.5 text-[11px] font-medium transition-colors hover:border-primary/40 sm:inline-flex",
                  paused && "border-warning/40 bg-warning/10",
                )}
                aria-label={paused ? "Reanudar actualización" : "Pausar actualización"}
              >
                <span
                  className={cn("h-2 w-2 rounded-full", paused ? "bg-warning" : STATUS_DOT[status])}
                  aria-hidden
                />
                <span className="text-foreground">
                  {paused ? "En pausa" : STATUS_LABEL[status]}
                </span>
                {lastUpdate && (
                  <span className="tabular-nums text-muted-foreground">{formatTime(lastUpdate)}</span>
                )}
                <span className="grid h-5 w-5 place-items-center rounded-full bg-background/70 text-foreground">
                  {paused ? <Play className="h-3 w-3" /> : <Pause className="h-3 w-3" />}
                </span>
              </button>
            </TooltipTrigger>
            <TooltipContent>
              {paused
                ? "Flujo pausado: los datos no se actualizan. Clic para reanudar."
                : "Flujo en tiempo real. Clic para pausar y analizar el estado actual."}
            </TooltipContent>
          </Tooltip>

          <Select value={filters.scenario} onValueChange={(v) => setScenario(v as typeof filters.scenario)}>
            <SelectTrigger className="h-8 w-[132px] text-xs" aria-label="Escenario activo">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.values(SCENARIO_CONFIG).map((s) => (
                <SelectItem key={s.id} value={s.id} disabled={!s.enabled} className="text-xs">
                  {s.label}
                  {!s.enabled && " (no disponible)"}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Selector de rango como grupo segmentado compacto. */}
          <div
            className="hidden items-center rounded-md border border-panel-border bg-muted/30 p-0.5 md:flex"
            role="group"
            aria-label="Rango temporal"
          >
            {RANGES.map((r) => (
              <button
                key={r.value}
                type="button"
                onClick={() => setFilters({ timeRange: r.value })}
                aria-pressed={filters.timeRange === r.value}
                className={cn(
                  "rounded px-2 py-1 text-[11px] font-medium transition-colors",
                  filters.timeRange === r.value
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {r.label}
              </button>
            ))}
          </div>

          <IconButton label="Actualizar datos" onClick={refresh}>
            <RefreshCw className="h-4 w-4" />
          </IconButton>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="icon" className="h-8 w-8" aria-label="Más opciones">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="text-xs">
              <DropdownMenuItem onClick={togglePause}>
                {paused ? <Play className="h-3.5 w-3.5" /> : <Pause className="h-3.5 w-3.5" />}
                {paused ? "Reanudar actualización" : "Pausar actualización"}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={toggleTheme}>
                {theme === "dark" ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
                {theme === "dark" ? "Tema claro" : "Tema oscuro"}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={goFullscreen}>
                <Maximize2 className="h-3.5 w-3.5" />
                Pantalla completa
              </DropdownMenuItem>
              {RANGES.map((r) => (
                <DropdownMenuItem
                  key={r.value}
                  className="md:hidden"
                  onClick={() => setFilters({ timeRange: r.value })}
                >
                  Rango: {r.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}

function IconButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button variant="outline" size="icon" className="h-8 w-8" onClick={onClick} aria-label={label}>
          {children}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}