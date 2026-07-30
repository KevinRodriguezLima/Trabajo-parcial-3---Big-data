import { createFileRoute } from "@tanstack/react-router";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { RegionChart } from "@/components/charts/RegionChart";

export const Route = createFileRoute("/regiones")({
  head: () => ({
    meta: [
      { title: "Compras por región del Perú | AudienceStream" },
      { name: "description", content: "Distribución territorial de compras, ingresos y conversión." },
      { property: "og:title", content: "Compras por región del Perú" },
      { property: "og:description", content: "Análisis regional de la actividad comercial simulada." },
    ],
  }),
  component: () => (
    <DashboardLayout title="Regiones" subtitle="Distribución territorial de la actividad comercial">
      <RegionChart />
    </DashboardLayout>
  ),
});