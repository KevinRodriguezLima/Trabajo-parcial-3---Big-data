import { createFileRoute } from "@tanstack/react-router";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { InfrastructurePanel } from "@/components/dashboard/InfrastructurePanel";

export const Route = createFileRoute("/arquitectura")({
  head: () => ({
    meta: [
      { title: "Arquitectura orientada a eventos | AudienceStream" },
      { name: "description", content: "Flujo Agentes → Kafka → Flink → Backend → Dashboard y salud de componentes." },
      { property: "og:title", content: "Arquitectura orientada a eventos" },
      { property: "og:description", content: "Documentación interactiva del pipeline de datos en tiempo real." },
    ],
  }),
  component: () => (
    <DashboardLayout title="Arquitectura" subtitle="Agentes → Kafka → Flink → Backend consumidor → Dashboard">
      <InfrastructurePanel />
    </DashboardLayout>
  ),
});