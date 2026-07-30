import { createFileRoute } from "@tanstack/react-router";
import { Users, Crown, TrendingUp } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { AudiencePanel } from "@/components/dashboard/AudiencePanel";
import { Panel, SectionHeading } from "@/components/common/Panel";
import { HeroMetricCard, InsightCard, SummaryBanner } from "@/components/common/Cards";
import { useRealtimeDashboard } from "@/hooks/useRealtimeDashboard";
import { buildInsights } from "@/lib/analytics";
import { formatInt, formatPercent } from "@/utils/format";

export const Route = createFileRoute("/audiencias")({
  head: () => ({
    meta: [
      { title: "Audiencias digitales detectadas | AudienceStream" },
      {
        name: "description",
        content:
          "Segmentos de audiencia detectados en tiempo real por Apache Flink: usuarios, reglas de detección y evolución.",
      },
      { property: "og:title", content: "Audiencias digitales detectadas | AudienceStream" },
      {
        property: "og:description",
        content: "Detalle de reglas, usuarios y evolución de cada audiencia sobre ventanas deslizantes de eventos.",
      },
    ],
  }),
  component: AudienciasPage,
});

function AudienciasPage() {
  const { snapshot, throughput, loading } = useRealtimeDashboard();
  const audiences = snapshot?.audiences ?? [];
  const totalUsers = audiences.reduce((a, b) => a + b.users, 0);
  const dominant = [...audiences].sort((a, b) => b.users - a.users)[0];
  const growingMost = [...audiences].sort((a, b) => b.change - a.change)[0];
  const insights = buildInsights(snapshot, throughput, "audiencias");

  const summary = snapshot
    ? `Se han segmentado ${formatInt(totalUsers)} usuarios en ${audiences.length} audiencias activas. La audiencia dominante es "${dominant?.label ?? "—"}" con ${formatPercent(dominant?.percentage ?? 0)} de la base, mientras "${growingMost?.label ?? "—"}" muestra la mayor variación (${growingMost ? growingMost.change.toFixed(1) : "0"} %).`
    : "Esperando el primer snapshot del backend consumidor.";

  return (
    <DashboardLayout title="Audiencias" subtitle="Segmentos detectados por reglas sobre ventanas deslizantes">
      {/* Nivel 1: resumen ejecutivo */}
      <SummaryBanner text={summary} />
      <div className="grid gap-4 sm:grid-cols-3">
        <HeroMetricCard
          label="Usuarios segmentados"
          value={loading ? "—" : formatInt(totalUsers)}
          icon={Users}
          tone="neutral"
          tooltip="Suma de usuarios asignados a alguna audiencia detectada por el job de Flink."
        />
        <HeroMetricCard
          label="Audiencia dominante"
          value={dominant ? dominant.label : "—"}
          context={dominant ? `${formatInt(dominant.users)} usuarios · ${formatPercent(dominant.percentage)}` : undefined}
          icon={Crown}
          tone="especial"
          tooltip="Audiencia con mayor cantidad absoluta de usuarios en el escenario activo."
        />
        <HeroMetricCard
          label="Mayor crecimiento"
          value={growingMost ? growingMost.label : "—"}
          delta={growingMost?.change}
          icon={TrendingUp}
          tone="positivo"
          tooltip="Audiencia con la mayor variación positiva respecto a la ventana anterior."
        />
      </div>

      {insights.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {insights.map((insight) => (
            <InsightCard key={insight.id} insight={insight} />
          ))}
        </div>
      )}

      {/* Nivel 2: panel principal con treemap y tarjetas */}
      <SectionHeading title="Detalle de audiencias" description="Explora, filtra y compara cada segmento detectado" />
      <AudiencePanel />

      {/* Nivel 3: panel técnico con reglas por audiencia */}
      <Panel
        title="Reglas de detección por audiencia"
        level="technical"
        collapsible
        defaultOpen={false}
        description="Tabla técnica con las reglas aplicadas por el job de audiencias de Apache Flink"
      >
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-panel-border text-muted-foreground">
                <th className="py-1.5 pr-3 font-medium">ID</th>
                <th className="py-1.5 pr-3 font-medium">Audiencia</th>
                <th className="py-1.5 pr-3 font-medium">Regla</th>
                <th className="py-1.5 pr-3 font-medium">Ventana</th>
                <th className="py-1.5 pr-3 font-medium">Usuarios</th>
              </tr>
            </thead>
            <tbody>
              {audiences.flatMap((a) =>
                a.rules.map((rule, i) => (
                  <tr key={`${a.id}-${i}`} className="border-b border-panel-border/60">
                    <td className="py-1.5 pr-3 font-mono text-[11px] text-muted-foreground">{a.id}</td>
                    <td className="py-1.5 pr-3 text-foreground">{a.label}</td>
                    <td className="py-1.5 pr-3 text-muted-foreground">{rule}</td>
                    <td className="py-1.5 pr-3 text-muted-foreground">ventana deslizante</td>
                    <td className="py-1.5 pr-3 tabular-nums text-foreground">{formatInt(a.users)}</td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
      </Panel>
    </DashboardLayout>
  );
}
