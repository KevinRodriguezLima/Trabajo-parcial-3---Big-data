import { createFileRoute } from "@tanstack/react-router";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { KpiCards } from "@/components/dashboard/KpiCards";
import { SectionHeading } from "@/components/common/Panel";
import { InsightCard, SummaryBanner } from "@/components/common/Cards";
import { ThroughputChart } from "@/components/charts/ThroughputChart";
import { EventsByTypeChart } from "@/components/charts/EventsByTypeChart";
import { AudiencePanel } from "@/components/dashboard/AudiencePanel";
import { TopViewedProducts, TopPurchasedProducts } from "@/components/dashboard/ProductRankings";
import { RegionChart } from "@/components/charts/RegionChart";
import { ConversionPanel } from "@/components/dashboard/ConversionPanel";
import { AlertsPanel } from "@/components/alerts/AlertsPanel";
import { InfrastructurePanel } from "@/components/dashboard/InfrastructurePanel";
import { SCENARIO_CONFIG } from "@/data/catalog";
import { useRealtimeDashboard } from "@/hooks/useRealtimeDashboard";
import { buildInsights, buildSystemSummary } from "@/lib/analytics";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Dashboard de Audiencias Digitales en Tiempo Real | AudienceStream" },
      {
        name: "description",
        content:
          "Dashboard en tiempo real de audiencias digitales sobre Apache Kafka y Apache Flink con diez indicadores y análisis de escenarios.",
      },
      { property: "og:title", content: "Dashboard de Audiencias Digitales en Tiempo Real" },
      {
        property: "og:description",
        content: "Monitoreo de eventos, audiencias, conversión y alertas de una arquitectura orientada a eventos.",
      },
    ],
  }),
  component: DashboardPage,
});

function DashboardPage() {
  const { filters, snapshot, throughput } = useRealtimeDashboard();
  const scenario = SCENARIO_CONFIG[filters.scenario];
  const summary = buildSystemSummary(snapshot, throughput, filters.timeRange);
  const insights = buildInsights(snapshot, throughput, "general");

  return (
    <DashboardLayout
      title="Dashboard de Audiencias Digitales en Tiempo Real"
      subtitle={`Escenario ${scenario.label}: ${scenario.description}`}
    >
      {/* Nivel 1 · Vista ejecutiva */}
      <SummaryBanner text={summary} />
      <KpiCards />
      {insights.length > 0 && (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {insights.map((insight) => (
            <InsightCard key={insight.id} insight={insight} />
          ))}
        </div>
      )}

      {/* Nivel 2 · Análisis operativo */}
      <SectionHeading
        title="Análisis operativo"
        description="Actividad del flujo, audiencias detectadas y embudo de conversión"
      />
      <div className="grid gap-4 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <ThroughputChart />
        </div>
        <AudiencePanel limit={6} />
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <EventsByTypeChart />
        <ConversionPanel />
      </div>

      {/* Nivel 3 · Detalle comercial y técnico */}
      <SectionHeading
        title="Detalle comercial y técnico"
        description="Rankings de catálogo, distribución territorial, alertas y salud del clúster"
      />
      <div className="grid gap-4 xl:grid-cols-2">
        <TopViewedProducts />
        <TopPurchasedProducts />
      </div>
      <RegionChart />
      <div className="grid gap-4 xl:grid-cols-2">
        <AlertsPanel limit={6} />
        <InfrastructurePanel />
      </div>
    </DashboardLayout>
  );
}
