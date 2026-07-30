import { X } from "lucide-react";
import { useRealtimeDashboard } from "@/hooks/useRealtimeDashboard";
import { DEFAULT_FILTERS } from "@/hooks/useRealtimeDashboard";
import type { GlobalFilters } from "@/types";

const LABELS: Partial<Record<keyof GlobalFilters, string>> = {
  region: "Región",
  profile: "Perfil",
  eventType: "Tipo de evento",
  source: "Fuente",
  alertLevel: "Severidad",
  audience: "Audiencia",
  product: "Producto",
  funnelStage: "Etapa",
};

/** Barra de contexto: muestra las selecciones cruzadas activas y permite quitarlas. */
export function FilterBar() {
  const { filters, setFilters, resetFilters, snapshot } = useRealtimeDashboard();

  const chips = (Object.keys(LABELS) as Array<keyof typeof LABELS>)
    .filter((key) => filters[key] !== DEFAULT_FILTERS[key])
    .map((key) => {
      let value = String(filters[key]);
      if (key === "audience") {
        value = snapshot?.audiences.find((a) => a.id === value)?.label ?? value;
      }
      if (key === "product") {
        value =
          snapshot?.top_viewed_products.find((p) => p.id === value)?.name ??
          snapshot?.top_purchased_products.find((p) => p.id === value)?.name ??
          value;
      }
      return { key, label: LABELS[key]!, value: value.replaceAll("_", " ").toLowerCase() };
    });

  const hasWindow = filters.window !== null;
  if (!chips.length && !hasWindow) return null;

  return (
    <div
      className="no-print flex flex-wrap items-center gap-2 border-b border-border bg-muted/30 px-4 py-2"
      aria-label="Filtros activos"
    >
      <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        Filtros cruzados
      </span>
      {chips.map((chip) => (
        <button
          key={chip.key}
          type="button"
          onClick={() => setFilters({ [chip.key]: DEFAULT_FILTERS[chip.key] } as Partial<GlobalFilters>)}
          className="inline-flex items-center gap-1.5 rounded-full border border-primary/40 bg-primary/10 px-2.5 py-1 text-[11px] font-medium text-primary transition-colors hover:bg-primary/20"
          aria-label={`Quitar filtro ${chip.label}`}
        >
          <span className="text-muted-foreground">{chip.label}:</span>
          <span className="capitalize">{chip.value}</span>
          <X className="h-3 w-3" aria-hidden />
        </button>
      ))}
      {hasWindow && (
        <button
          type="button"
          onClick={() => setFilters({ window: null })}
          className="inline-flex items-center gap-1.5 rounded-full border border-info/40 bg-info/10 px-2.5 py-1 text-[11px] font-medium text-info transition-colors hover:bg-info/20"
        >
          Intervalo {filters.window!.from} – {filters.window!.to}
          <X className="h-3 w-3" aria-hidden />
        </button>
      )}
      <button
        type="button"
        onClick={resetFilters}
        className="ml-auto text-[11px] font-medium text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
      >
        Limpiar todo
      </button>
    </div>
  );
}