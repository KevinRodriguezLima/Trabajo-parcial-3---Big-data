import { useMemo } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Activity, Layers, ShieldAlert } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { EventsByTypeChart } from "@/components/charts/EventsByTypeChart";
import { ThroughputChart } from "@/components/charts/ThroughputChart";
import { EventHeatmap } from "@/components/charts/EventHeatmap";
import { Panel, SectionHeading } from "@/components/common/Panel";
import { CompactMetricCard, SummaryBanner } from "@/components/common/Cards";
import { useRealtimeDashboard } from "@/hooks/useRealtimeDashboard";
import { buildSystemSummary } from "@/lib/analytics";
import { formatEps, formatInt, formatPercent } from "@/utils/format";

export const Route = createFileRoute("/eventos")({
  head: () => ({
    meta: [
      { title: "Eventos, throughput y mapa de calor | AudienceStream" },
      {
        name: "description",
        content: "Flujo de eventos ingeridos desde Apache Kafka: throughput, anomalías y distribución por tipo.",
      },
      { property: "og:title", content: "Eventos, throughput y mapa de calor" },
      {
        property: "og:description",
        content: "Análisis del flujo de eventos procesado por Apache Flink sobre Apache Kafka.",
      },
    ],
  }),
  component: EventosPage,
});

function EventosPage() {
  const { snapshot, throughput, filters, loading } = useRealtimeDashboard();

  const summary = useMemo(
    () => buildSystemSummary(snapshot, throughput, filters.timeRange),
    [snapshot, throughput, filters.timeRange],
  );

  const failed = snapshot?.events_by_type.find((e) => e.event_type === "PAYMENT_FAILED");
  const totalEvents = snapshot?.events_by_type.reduce((a, b) => a + b.count, 0) ?? 0;

  return (
    <DashboardLayout title="Eventos" subtitle="Distribución, throughput y detección de anomalías del flujo de eventos">
      <div className="space-y-5">
        {/* Nivel 1: resumen ejecutivo y métricas clave del flujo */}
        <SummaryBanner text={summary} />
        <div className="grid gap-3 sm:grid-cols-3">
          <CompactMetricCard
            label="Eventos por segundo (actual)"
            value={loading || !snapshot ? "—" : formatEps(snapshot.metrics.events_per_second)}
            tone="neutral"
            tooltip="Throughput instantáneo reportado en el último snapshot del backend consumidor."
          />
          <CompactMetricCard
            label="Eventos totales acumulados"
            value={loading ? "—" : formatInt(totalEvents)}
            tone="especial"
            tooltip="Suma de todos los tipos de evento acumulados desde el inicio de la ejecución del escenario."
          />
          <CompactMetricCard
            label="Pagos fallidos"
            value={loading || !failed ? "—" : formatPercent(failed.percentage)}
            tone={failed && failed.percentage > 1.5 ? "critico" : "neutral"}
            tooltip="Porcentaje de eventos PAYMENT_FAILED sobre el total del flujo."
          />
        </div>

        {/* Nivel 2: throughput principal y mapa de calor */}
        <SectionHeading
          title="Flujo temporal"
          description="Actividad por segundo y concentración por tipo de evento en el tiempo"
        />
        <ThroughputChart />
        <EventHeatmap />

        {/* Nivel 3: distribución por tipo y detalle técnico */}
        <SectionHeading title="Composición del flujo" description="Detalle por tipo de evento, categoría y fuente" />
        <EventsByTypeChart />

        <Panel
          level="technical"
          title="Detalle técnico: tipos de evento y fuentes"
          description="Tabla de soporte para auditoría del sobre común de eventos"
          collapsible
          defaultOpen={false}
          tooltip="Datos crudos del snapshot vigente: conteo por tipo de evento y participación por fuente de ingesta (WEB, MOBILE, IOT, VEHICLE, POS)."
        >
          {!snapshot ? (
            <p className="text-xs text-muted-foreground">Sin datos disponibles.</p>
          ) : (
            <div className="grid gap-6 lg:grid-cols-2">
              <div>
                <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  <Layers className="h-3.5 w-3.5" aria-hidden /> Tipos de evento
                </h3>
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-panel-border text-left text-muted-foreground">
                      <th className="py-1.5 font-medium">Tipo</th>
                      <th className="py-1.5 font-medium">Categoría</th>
                      <th className="py-1.5 text-right font-medium">Conteo</th>
                      <th className="py-1.5 text-right font-medium">%</th>
                    </tr>
                  </thead>
                  <tbody>
                    {snapshot.events_by_type.map((e) => (
                      <tr key={e.event_type} className="border-b border-panel-border/60 last:border-0">
                        <td className="py-1.5 text-foreground">{e.event_type}</td>
                        <td className="py-1.5 text-muted-foreground">{e.category}</td>
                        <td className="py-1.5 text-right tabular-nums text-foreground">{formatInt(e.count)}</td>
                        <td className="py-1.5 text-right tabular-nums text-muted-foreground">
                          {e.percentage.toFixed(2)} %
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div>
                <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  <Activity className="h-3.5 w-3.5" aria-hidden /> Fuentes de ingesta
                </h3>
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-panel-border text-left text-muted-foreground">
                      <th className="py-1.5 font-medium">Fuente</th>
                      <th className="py-1.5 text-right font-medium">Eventos</th>
                      <th className="py-1.5 text-right font-medium">Participación</th>
                    </tr>
                  </thead>
                  <tbody>
                    {snapshot.sources.map((s) => (
                      <tr key={s.source} className="border-b border-panel-border/60 last:border-0">
                        <td className="py-1.5 text-foreground">{s.source}</td>
                        <td className="py-1.5 text-right tabular-nums text-foreground">{formatInt(s.events)}</td>
                        <td className="py-1.5 text-right tabular-nums text-muted-foreground">
                          {(s.share * 100).toFixed(1)} %
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {snapshot.alerts.some((a) => a.component.toLowerCase().includes("kafka") && a.status === "ACTIVA") && (
                  <p className="mt-3 flex items-center gap-1.5 text-[11px] text-warning">
                    <ShieldAlert className="h-3.5 w-3.5" aria-hidden />
                    Hay alertas activas sobre el clúster Kafka; revisa la sección de Alertas.
                  </p>
                )}
              </div>
            </div>
          )}
        </Panel>
      </div>
    </DashboardLayout>
  );
}
