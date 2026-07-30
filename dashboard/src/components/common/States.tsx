import type { ReactNode } from "react";
import { AlertTriangle, Inbox, WifiOff } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

export function PanelSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3" aria-busy="true" aria-label="Cargando datos">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-8 w-full" />
      ))}
    </div>
  );
}

export function ChartSkeleton({ height = 260 }: { height?: number }) {
  return <Skeleton className="w-full" style={{ height }} aria-label="Cargando gráfico" />;
}

export function EmptyState({
  title = "Sin datos para los filtros seleccionados",
  description = "Ajusta los filtros globales o cambia de escenario para ver resultados.",
  action,
}: {
  title?: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
      <Inbox className="h-8 w-8 text-muted-foreground" aria-hidden />
      <p className="text-sm font-medium text-foreground">{title}</p>
      <p className="max-w-sm text-xs text-muted-foreground">{description}</p>
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-10 text-center">
      <AlertTriangle className="h-8 w-8 text-critical" aria-hidden />
      <p className="text-sm font-medium text-foreground">Ocurrió un error al recibir datos</p>
      <p className="max-w-sm text-xs text-muted-foreground">{message}</p>
      {onRetry && (
        <Button size="sm" variant="outline" onClick={onRetry}>
          Reintentar
        </Button>
      )}
    </div>
  );
}

export function DisconnectedState({ onRetry }: { onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-10 text-center">
      <WifiOff className="h-8 w-8 text-warning" aria-hidden />
      <p className="text-sm font-medium text-foreground">Sin conexión con el backend consumidor</p>
      <p className="max-w-sm text-xs text-muted-foreground">
        No se recibe el flujo de mensajes. Verifica que el servicio FastAPI y el clúster
        Kafka/Flink estén activos, o cambia a modo demostración desde Configuración.
      </p>
      {onRetry && (
        <Button size="sm" variant="outline" onClick={onRetry}>
          Reintentar conexión
        </Button>
      )}
    </div>
  );
}