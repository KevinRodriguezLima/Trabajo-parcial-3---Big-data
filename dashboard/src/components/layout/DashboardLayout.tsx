import { useState, type ReactNode } from "react";
import { AppSidebar, MobileNav } from "./AppSidebar";
import { Topbar } from "./Topbar";
import { FilterBar } from "./FilterBar";

/** Estructura general: barra lateral colapsable + barra superior + contenido. */
export function DashboardLayout({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="flex min-h-screen w-full bg-background text-foreground">
      <AppSidebar collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar title={title} subtitle={subtitle} />
        <FilterBar />
        <MobileNav />
        <main className="print-full flex-1 space-y-5 p-4 lg:p-5">{children}</main>
        <footer className="no-print border-t border-border px-4 py-3 text-xs text-muted-foreground">
          Plataforma Inteligente para Simulación y Análisis de Audiencias Digitales en Tiempo Real ·
          Arquitecturas Orientadas a Eventos · BIGDATA 2026A
        </footer>
      </div>
    </div>
  );
}