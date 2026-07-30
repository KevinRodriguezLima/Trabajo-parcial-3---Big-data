import { Link, useRouterState } from "@tanstack/react-router";
import {
  Activity,
  BarChart3,
  Bell,
  ChevronLeft,
  FlaskConical,
  LayoutDashboard,
  MapPinned,
  Network,
  Package,
  Settings,
  Users,
  Waypoints,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { APP_CONFIG } from "@/services/config";
import { useRealtimeDashboard } from "@/hooks/useRealtimeDashboard";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/audiencias", label: "Audiencias", icon: Users },
  { to: "/eventos", label: "Eventos", icon: Activity },
  { to: "/productos", label: "Productos", icon: Package },
  { to: "/regiones", label: "Regiones", icon: MapPinned },
  { to: "/alertas", label: "Alertas", icon: Bell },
  { to: "/experimentos", label: "Experimentos", icon: FlaskConical },
  { to: "/arquitectura", label: "Arquitectura", icon: Network },
  { to: "/configuracion", label: "Configuración", icon: Settings },
] as const;

export function AppSidebar({
  collapsed,
  onToggle,
}: {
  collapsed: boolean;
  onToggle: () => void;
}) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const { status, snapshot } = useRealtimeDashboard();
  const connected = status === "CONECTADO" || status === "DEMO";

  return (
    <aside
      className={cn(
        "no-print sticky top-0 z-30 hidden h-screen shrink-0 flex-col border-r border-sidebar-border bg-sidebar transition-all duration-200 md:flex",
        collapsed ? "w-16" : "w-60",
      )}
      aria-label="Navegación principal"
    >
      <div className="flex h-14 items-center gap-2 border-b border-sidebar-border px-3">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary/15 text-primary">
          <Waypoints className="h-4.5 w-4.5" aria-hidden />
        </span>
        {!collapsed && (
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-sidebar-foreground">
              {APP_CONFIG.appName}
            </p>
            <p className="truncate text-[10px] uppercase tracking-wider text-muted-foreground">
              Kafka · Flink
            </p>
          </div>
        )}
        <button
          type="button"
          onClick={onToggle}
          aria-label={collapsed ? "Expandir barra lateral" : "Colapsar barra lateral"}
          className="ml-auto rounded-md p-1 text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground"
        >
          <ChevronLeft className={cn("h-4 w-4 transition-transform", collapsed && "rotate-180")} aria-hidden />
        </button>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto p-2">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.to;
          const link = (
            <Link
              key={item.to}
              to={item.to}
              className={cn(
                "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors",
                active
                  ? "bg-sidebar-accent font-medium text-sidebar-primary shadow-[inset_2px_0_0_0_var(--sidebar-primary)]"
                  : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-foreground",
                collapsed && "justify-center px-0",
              )}
              aria-current={active ? "page" : undefined}
            >
              <item.icon className="h-4 w-4 shrink-0" aria-hidden />
              {!collapsed && <span className="truncate">{item.label}</span>}
            </Link>
          );
          return collapsed ? (
            <Tooltip key={item.to}>
              <TooltipTrigger asChild>{link}</TooltipTrigger>
              <TooltipContent side="right">{item.label}</TooltipContent>
            </Tooltip>
          ) : (
            link
          );
        })}
      </nav>

      <div className="space-y-2 border-t border-sidebar-border p-3 text-xs">
        <div className="flex items-center gap-2">
          <span
            className={cn("h-2 w-2 rounded-full", connected ? "bg-success" : "bg-critical")}
            aria-hidden
          />
          {!collapsed && (
            <span className="text-muted-foreground">
              {connected ? "Sistema conectado" : "Sistema sin conexión"}
            </span>
          )}
        </div>
        {!collapsed && (
          <>
            <p className="flex items-center gap-1.5 text-muted-foreground">
              <BarChart3 className="h-3.5 w-3.5" aria-hidden />
              {snapshot ? `${snapshot.metrics.events_per_second.toFixed(1)} eps` : "Sin flujo"}
            </p>
            <p className="text-muted-foreground">Versión {APP_CONFIG.version}</p>
            <p className="font-medium text-sidebar-foreground">{APP_CONFIG.course}</p>
          </>
        )}
      </div>
    </aside>
  );
}

export function MobileNav() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  return (
    <nav
      className="no-print flex gap-1 overflow-x-auto border-b border-border bg-sidebar px-2 py-2 md:hidden"
      aria-label="Navegación móvil"
    >
      {NAV_ITEMS.map((item) => (
        <Link
          key={item.to}
          to={item.to}
          className={cn(
            "flex shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs",
            pathname === item.to
              ? "bg-sidebar-accent font-medium text-sidebar-primary"
              : "text-muted-foreground",
          )}
        >
          <item.icon className="h-3.5 w-3.5" aria-hidden />
          {item.label}
        </Link>
      ))}
    </nav>
  );
}