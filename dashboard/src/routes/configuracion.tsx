import { createFileRoute } from "@tanstack/react-router";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Panel } from "@/components/common/Panel";
import { APP_CONFIG } from "@/services/config";

export const Route = createFileRoute("/configuracion")({
  head: () => ({
    meta: [
      { title: "Configuración de la plataforma | AudienceStream" },
      { name: "description", content: "Modo de transporte de datos y parámetros de conexión del dashboard." },
      { property: "og:title", content: "Configuración de la plataforma" },
      { property: "og:description", content: "Modo simulación local o conexión real por WebSocket/SSE." },
    ],
  }),
  component: () => (
    <DashboardLayout title="Configuración" subtitle="Transporte de datos y parámetros de conexión">
      <Panel title="Fuente de datos" description="Definida por variables de entorno del proyecto">
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          {Object.entries(APP_CONFIG).map(([k, v]) => (
            <div key={k} className="rounded-md border border-panel-border bg-muted/30 px-3 py-2">
              <dt className="text-[11px] uppercase text-muted-foreground">{k}</dt>
              <dd className="font-mono text-xs text-foreground">{String(v)}</dd>
            </div>
          ))}
        </dl>
      </Panel>
    </DashboardLayout>
  ),
});