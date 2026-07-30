import { createFileRoute } from "@tanstack/react-router";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { TopPurchasedProducts, TopViewedProducts } from "@/components/dashboard/ProductRankings";

export const Route = createFileRoute("/productos")({
  head: () => ({
    meta: [
      { title: "Productos más visitados y comprados | AudienceStream" },
      { name: "description", content: "Rankings de productos por vistas, unidades, órdenes e ingresos." },
      { property: "og:title", content: "Productos más visitados y comprados" },
      { property: "og:description", content: "Ranking comercial consolidado por Apache Flink." },
    ],
  }),
  component: () => (
    <DashboardLayout title="Productos" subtitle="Rankings de visitas y compras del catálogo">
      <TopViewedProducts />
      <TopPurchasedProducts />
    </DashboardLayout>
  ),
});