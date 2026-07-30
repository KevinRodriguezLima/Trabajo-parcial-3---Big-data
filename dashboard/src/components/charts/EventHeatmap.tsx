import { useMemo } from "react";
import { Panel } from "@/components/common/Panel";
import { ChartSkeleton, EmptyState } from "@/components/common/States";
import { useRealtimeDashboard } from "@/hooks/useRealtimeDashboard";
import { buildHeatmap } from "@/lib/analytics";
import { CATEGORY_COLOR, eventColor } from "@/lib/palette";
import { EVENT_CATEGORY } from "@/data/catalog";
import { EVENT_TYPES } from "@/types";
import { formatInt } from "@/utils/format";
import { cn } from "@/lib/utils";

/** Matriz tipo de evento × intervalo temporal, con intensidad de color por categoría. */
export function EventHeatmap() {
  const { throughput, loading, filters, setFilters } = useRealtimeDashboard();

  const heatmap = useMemo(() => buildHeatmap(throughput, EVENT_TYPES), [throughput]);

  const toggleRow = (eventType: (typeof EVENT_TYPES)[number]) => {
    setFilters({ eventType: filters.eventType === eventType ? "TODOS" : eventType });
  };

  const toggleColumn = (bucket: string, index: number) => {
    if (filters.window?.from === bucket) {
      setFilters({ window: null });
      return;
    }
    const nextBucket = heatmap.buckets[index + 1] ?? bucket;
    setFilters({ window: { from: bucket, to: nextBucket } });
  };

  return (
    <Panel
      title="Mapa de calor: tipo de evento × intervalo"
      description="Volumen relativo de cada tipo de evento a lo largo de la ventana visible"
      tooltip="Cada celda estima el volumen de eventos de un tipo dentro de un intervalo temporal, ponderado por su peso relativo en el flujo. Haz clic en una fila para filtrar por tipo de evento o en una columna para fijar la ventana temporal."
      actions={
        <ul className="flex flex-wrap gap-3 text-[11px] text-muted-foreground">
          {Object.entries(CATEGORY_COLOR).map(([key, color]) => (
            <li key={key} className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-sm" style={{ background: color }} aria-hidden />
              {key}
            </li>
          ))}
        </ul>
      }
    >
      {loading ? (
        <ChartSkeleton height={320} />
      ) : heatmap.buckets.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="overflow-x-auto">
          <div
            className="grid min-w-[720px] gap-1"
            style={{ gridTemplateColumns: `140px repeat(${heatmap.buckets.length}, minmax(36px, 1fr))` }}
          >
            {/* Encabezado de columnas (intervalos) */}
            <div />
            {heatmap.buckets.map((bucket, i) => {
              const active = filters.window?.from === bucket;
              return (
                <button
                  key={`${bucket}-${i}`}
                  type="button"
                  onClick={() => toggleColumn(bucket, i)}
                  className={cn(
                    "truncate rounded px-1 py-1 text-center text-[10px] text-muted-foreground hover:bg-muted",
                    active && "bg-primary/15 font-semibold text-primary",
                  )}
                  aria-label={`Filtrar ventana temporal ${bucket}`}
                >
                  {bucket}
                </button>
              );
            })}

            {heatmap.rows.map((row) => {
              const rowActive = filters.eventType === row.eventType;
              const dimmed = filters.eventType !== "TODOS" && !rowActive;
              return (
                <div key={row.eventType} className="contents">
                  <button
                    type="button"
                    onClick={() => toggleRow(row.eventType)}
                    className={cn(
                      "flex items-center gap-1.5 truncate rounded px-1.5 py-1 text-left text-[11px] font-medium hover:bg-muted",
                      rowActive ? "bg-primary/10 text-primary" : "text-foreground",
                      dimmed && "opacity-50",
                    )}
                    aria-label={`Filtrar por tipo de evento ${row.eventType}`}
                    title={`${row.eventType} · ${formatInt(row.total)} eventos estimados`}
                  >
                    <span
                      className="h-2 w-2 shrink-0 rounded-sm"
                      style={{ background: eventColor(row.eventType) }}
                      aria-hidden
                    />
                    {row.eventType}
                  </button>
                  {row.cells.map((cell, ci) => {
                    const colActive = filters.window?.from === cell.bucket;
                    const cellDimmed = dimmed || (filters.window && !colActive);
                    return (
                      <button
                        key={`${row.eventType}-${ci}`}
                        type="button"
                        onClick={() => toggleColumn(cell.bucket, ci)}
                        className={cn(
                          "aspect-square min-h-[24px] rounded-sm transition-opacity",
                          cellDimmed && "opacity-40",
                        )}
                        style={{
                          background: eventColor(row.eventType),
                          opacity: cellDimmed ? undefined : 0.15 + cell.intensity * 0.8,
                        }}
                        aria-label={`${row.eventType} en ${cell.bucket}: ${formatInt(cell.value)} eventos`}
                        title={`${row.eventType} · ${cell.bucket} · ${formatInt(cell.value)} eventos (${(cell.intensity * 100).toFixed(0)} % del máximo)`}
                      />
                    );
                  })}
                </div>
              );
            })}
          </div>
          <p className="mt-3 text-[11px] text-muted-foreground">
            Categoría por color: {Object.entries(EVENT_CATEGORY).length ? "según leyenda superior" : ""} · La intensidad
            del relleno indica la proporción respecto al valor máximo de la matriz ({formatInt(heatmap.max)}).
          </p>
        </div>
      )}
    </Panel>
  );
}
