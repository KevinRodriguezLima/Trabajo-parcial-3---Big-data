import { Activity, AlertTriangle, Coins, Percent, ShoppingCart, Users } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { CompactMetricCard, HeroMetricCard, type MetricTone } from "@/components/common/Cards";
import { useRealtimeDashboard } from "@/hooks/useRealtimeDashboard";
import { formatCompactCurrency, formatEps, formatInt, formatRatioAsPercent } from "@/utils/format";

/**
 * Nivel 1 de la jerarquía: tres métricas ejecutivas de gran tamaño y tres
 * métricas compactas de apoyo (indicadores 1, 2, 9 y 10 más contexto comercial).
 */
export function KpiCards() {
  const { snapshot, loading } = useRealtimeDashboard();

  if (loading || !snapshot) {
    return (
      <div className="grid gap-3 lg:grid-cols-[repeat(3,minmax(0,1fr))]">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-[132px] w-full rounded-lg" />
        ))}
      </div>
    );
  }

  const m = snapshot.metrics;
  const d = snapshot.deltas;
  const s = snapshot.sparklines;

  const topRegion = snapshot.regions[0];
  const criticas = snapshot.alerts.filter(
    (a) => a.level === "CRITICAL" && a.status === "ACTIVA",
  ).length;

  return (
    <div className="space-y-3">
      <div className="grid gap-3 lg:grid-cols-3">
        <HeroMetricCard
          label="Usuarios activos"
          value={formatInt(m.active_users)}
          delta={d.active_users}
          spark={s.active_users}
          icon={Users}
          tone="neutral"
          context={topRegion ? `Mayor concentración en ${topRegion.region}` : undefined}
          tooltip="Usuarios únicos con al menos un evento en la ventana deslizante procesada por Flink."
        />
        <HeroMetricCard
          label="Eventos por segundo"
          value={formatEps(m.events_per_second)}
          delta={d.events_per_second}
          spark={s.events_per_second}
          icon={Activity}
          tone="especial"
          context={`Latencia media ${formatInt(m.average_latency_ms)} ms`}
          tooltip="Throughput instantáneo de eventos ingeridos desde los topics de Kafka."
        />
        <HeroMetricCard
          label="Conversión de compras"
          value={formatRatioAsPercent(m.purchase_conversion)}
          delta={d.purchase_conversion}
          spark={s.purchase_conversion}
          icon={Percent}
          tone={m.purchase_conversion >= 0.1 ? "positivo" : "neutral"}
          context={`${formatInt(m.total_purchases)} compras confirmadas`}
          tooltip="Relación entre eventos PURCHASE y eventos VIEW_PRODUCT acumulados."
        />
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <CompactMetricCard
          label="Compras totales"
          value={formatInt(m.total_purchases)}
          delta={d.total_purchases}
          spark={s.total_purchases}
          tone="positivo"
          tooltip="Eventos PURCHASE confirmados durante la ejecución del escenario."
        />
        <CompactMetricCard
          label="Ingresos acumulados"
          value={formatCompactCurrency(m.total_revenue)}
          delta={d.total_revenue}
          spark={s.total_revenue}
          tone="positivo"
          tooltip="Suma del monto de todas las compras confirmadas del escenario activo."
        />
        <CompactMetricCard
          label="Alertas activas"
          value={formatInt(m.active_alerts)}
          delta={d.active_alerts}
          spark={s.active_alerts}
          inverseDelta
          tone={m.active_alerts > 5 ? "critico" : "neutral"}
          tooltip="Alertas emitidas por el job de detección que aún no fueron resueltas."
        />
        <CompactMetricCard
          label="Alertas críticas"
          value={formatInt(criticas)}
          spark={s.active_alerts}
          inverseDelta
          tone={(criticas > 0 ? "critico" : "positivo") as MetricTone}
          tooltip="Alertas de severidad CRITICAL que siguen sin reconocerse."
        />
      </div>
    </div>
  );
}
