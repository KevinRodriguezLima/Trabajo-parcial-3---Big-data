/**
 * Paleta semántica del sistema de visual analytics.
 * Azul = actividad general · Verde = compras/ingresos · Violeta = IoT
 * Ámbar = advertencias · Rojo = crítico · Gris = contexto secundario.
 */
import type { EventCategory, EventType } from "@/types";
import { EVENT_CATEGORY } from "@/data/catalog";

export const CATEGORY_COLOR: Record<EventCategory, string> = {
  DIGITAL: "var(--color-info)",
  COMPRAS: "var(--color-success)",
  IOT: "var(--color-special)",
  SISTEMA: "var(--color-warning)",
};

export const CATEGORY_LABEL: Record<EventCategory, string> = {
  DIGITAL: "Digital",
  COMPRAS: "Compras",
  IOT: "IoT",
  SISTEMA: "Sistema",
};

export function eventColor(type: EventType): string {
  if (type === "PAYMENT_FAILED") return "var(--color-critical)";
  return CATEGORY_COLOR[EVENT_CATEGORY[type]];
}

/** Serie de colores para categorías comerciales, sin repetir el mismo azul. */
export const SERIES_COLORS = [
  "var(--color-info)",
  "var(--color-success)",
  "var(--color-special)",
  "var(--color-warning)",
  "var(--color-critical)",
  "var(--color-primary)",
];

export function seriesColor(index: number): string {
  return SERIES_COLORS[index % SERIES_COLORS.length];
}

export const CHART_TOOLTIP_STYLE = {
  background: "var(--color-popover)",
  border: "1px solid var(--color-border)",
  borderRadius: 10,
  fontSize: 12,
  color: "var(--color-popover-foreground)",
  boxShadow: "var(--shadow-panel)",
} as const;