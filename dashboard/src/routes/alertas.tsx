import { useMemo } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Download } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { AlertsPanel } from "@/components/alerts/AlertsPanel";
import { InfrastructurePanel } from "@/components/dashboard/InfrastructurePanel";
import { HeroMetricCard, InsightCard, SummaryBanner } from "@/components/common/Cards";
import { Panel, SectionHeading } from "@/components/common/Panel";
import { EmptyState } from "@/components/common/States";
import { ALERT_STYLE } from "@/components/common/StatusIndicators";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useRealtimeDashboard } from "@/hooks/useRealtimeDashboard";
import { buildInsights, buildSystemSummary } from "@/lib/analytics";
import { downloadFile, formatTime, toCsv } from "@/utils/format";

export const Route = createFileRoute("/alertas")({
  head: () => ({
    meta: [
      { title: "Alertas y estado de la plataforma | AudienceStream" },
      {
        name: "description",
        content:
          "Gestión de alertas críticas emitidas por Apache Flink y salud de la infraestructura Kafka/Flink/Backend en tiempo real.",
      },
      { property: "og:title", content: "Alertas y estado de la plataforma | AudienceStream" },
      {
        property: "og:description",
        content:
          "Panel de alertas en tiempo real con reconocimiento, resolución y diagnóstico de infraestructura.",
      },
    ],
  }),
  component: AlertasPage,
});

function AlertasPage() {
  const { snapshot, throughput, filters } = useRealtimeDashboard();

  const summary = buildSystemSummary(snapshot, throughput, filters.timeRange);
  const insights = useMemo(
    () => buildInsights(snapshot, throughput, "alertas"),
    [snapshot, throughput],
  );

  const alerts = useMemo(() => snapshot?.alerts ?? [], [snapshot?.alerts]);
  const activeAlerts = alerts.filter((a) => a.status === "ACTIVA");
  const criticalActive = activeAlerts.filter((a) => a.level === "CRITICAL").length;
  const degradedComponents = (snapshot?.infrastructure ?? []).filter(
    (c) => c.status !== "OPERATIVO",
  ).length;

  // Tiempo medio de reconocimiento estimado: heurística por antigüedad de alertas ya reconocidas/resueltas.
  const avgAckMinutes = useMemo(() => {
    const acked = alerts.filter((a) => a.status !== "ACTIVA");
    if (acked.length === 0) return 0;
    const total = acked.reduce((sum, a) => {
      const ageMin = Math.max(0.5, (Date.now() - new Date(a.timestamp).getTime()) / 60000);
      return sum + Math.min(ageMin, 45);
    }, 0);
    return total / acked.length;
  }, [alerts]);

  const handleExport = () => {
    const rows = alerts.map((a) => ({
      id: a.id,
      nivel: a.level,
      titulo: a.title,
      descripcion: a.description,
      componente: a.component,
      escenario: a.scenario,
      estado: a.status,
      timestamp: formatTime(a.timestamp),
    }));
    downloadFile(
      `alertas-${snapshot?.scenario ?? "sistema"}.csv`,
      toCsv(rows),
      "text/csv;charset=utf-8;",
    );
  };

  return (
    <DashboardLayout
      title="Alertas"
      subtitle="Gestión de alertas emitidas por los jobs de procesamiento"
    >
      {/* Nivel 1: resumen ejecutivo */}
      <SummaryBanner text={summary} />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <HeroMetricCard
          label="Alertas activas"
          value={String(activeAlerts.length)}
          tone={activeAlerts.length > 0 ? "critico" : "positivo"}
          tooltip="Alertas emitidas que aún no han sido reconocidas ni resueltas."
        />
        <HeroMetricCard
          label="Alertas críticas"
          value={String(criticalActive)}
          tone={criticalActive > 0 ? "critico" : "positivo"}
          tooltip="Alertas de severidad crítica en estado activo."
        />
        <HeroMetricCard
          label="Tiempo medio de reconocimiento"
          value={`${avgAckMinutes.toFixed(1)} min`}
          tone="neutral"
          tooltip="Estimación basada en la antigüedad de las alertas ya reconocidas o resueltas del snapshot actual."
        />
        <HeroMetricCard
          label="Componentes degradados"
          value={String(degradedComponents)}
          tone={degradedComponents > 0 ? "critico" : "positivo"}
          tooltip="Componentes de infraestructura que no están en estado OPERATIVO."
        />
      </div>

      {insights.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {insights.map((i) => (
            <InsightCard key={i.id} insight={i} />
          ))}
        </div>
      )}

      {/* Nivel 2: gestión completa de alertas */}
      <SectionHeading
        title="Gestión de alertas"
        description="Filtra, reconoce y resuelve las alertas activas"
      />
      <AlertsPanel maxHeight={640} />

      {/* Nivel 3: infraestructura + detalle técnico */}
      <SectionHeading title="Infraestructura y detalle técnico" />
      <InfrastructurePanel />

      <Panel
        title="Detalle técnico de alertas"
        level="technical"
        collapsible
        defaultOpen={false}
        description="Listado tabular completo para exportación y auditoría"
        actions={
          <Button
            size="sm"
            variant="outline"
            className="h-7 gap-1.5 text-xs"
            onClick={handleExport}
          >
            <Download className="h-3.5 w-3.5" aria-hidden /> Exportar CSV
          </Button>
        }
      >
        {alerts.length === 0 ? (
          <EmptyState
            title="Sin alertas registradas"
            description="No hay alertas en el escenario actual."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-panel-border text-left uppercase tracking-wide text-muted-foreground">
                  <th className="py-2 pr-2 font-medium">Título</th>
                  <th className="px-2 py-2 font-medium">Nivel</th>
                  <th className="px-2 py-2 font-medium">Componente</th>
                  <th className="px-2 py-2 font-medium">Estado</th>
                  <th className="py-2 pl-2 text-right font-medium">Hora</th>
                </tr>
              </thead>
              <tbody>
                {alerts.map((a) => (
                  <tr key={a.id} className="border-b border-panel-border/60 last:border-0">
                    <td className="py-2 pr-2 font-medium text-foreground">{a.title}</td>
                    <td className="px-2 py-2">
                      <Badge
                        variant="outline"
                        className={`text-[10px] ${ALERT_STYLE[a.level].badge}`}
                      >
                        {ALERT_STYLE[a.level].label}
                      </Badge>
                    </td>
                    <td className="px-2 py-2">{a.component}</td>
                    <td className="px-2 py-2">{a.status}</td>
                    <td className="py-2 pl-2 text-right tabular-nums">{formatTime(a.timestamp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </DashboardLayout>
  );
}
