import { createFileRoute } from "@tanstack/react-router";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Panel } from "@/components/common/Panel";
import { SCENARIO_CONFIG } from "@/data/catalog";
import type { Scenario } from "@/types";
import { formatInt, formatRatioAsPercent } from "@/utils/format";

export const Route = createFileRoute("/experimentos")({
  head: () => ({
    meta: [
      { title: "Comparación de escenarios simulados | AudienceStream" },
      { name: "description", content: "Comparativa de Base, Navidad, Cyber Monday y Black Friday." },
      { property: "og:title", content: "Comparación de escenarios simulados" },
      { property: "og:description", content: "Parámetros técnicos de carga, conversión y latencia por escenario." },
    ],
  }),
  component: () => (
    <DashboardLayout title="Experimentos" subtitle="Parámetros comparados de los escenarios de simulación">
      <Panel title="Escenarios" description="Configuración de carga usada por el generador de eventos">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-panel-border text-left text-[11px] uppercase text-muted-foreground">
                <th className="py-2 pr-2 font-medium">Escenario</th>
                <th className="px-2 py-2 text-right font-medium">Eventos/seg</th>
                <th className="px-2 py-2 text-right font-medium">Conversión</th>
                <th className="py-2 pl-2 text-right font-medium">Latencia base</th>
              </tr>
            </thead>
            <tbody>
              {(Object.keys(SCENARIO_CONFIG) as Scenario[]).map((s) => {
                const c = SCENARIO_CONFIG[s];
                return (
                  <tr key={s} className="border-b border-panel-border/60 last:border-0">
                    <td className="py-2 pr-2 font-medium">{c.label}</td>
                    <td className="px-2 py-2 text-right tabular-nums">
                      {formatInt(c.epsMin)} – {formatInt(c.epsMax)}
                    </td>
                    <td className="px-2 py-2 text-right tabular-nums">{formatRatioAsPercent(c.conversion)}</td>
                    <td className="py-2 pl-2 text-right tabular-nums">{c.latency} ms</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Panel>
    </DashboardLayout>
  ),
});