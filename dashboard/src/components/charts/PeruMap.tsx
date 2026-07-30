/**
 * Mapa coroplético simplificado del Perú (SVG estilizado, no geoespacial real).
 * Agrupa regiones por macrorregión con intensidad de color según la métrica activa.
 */
import { useMemo, useState } from "react";
import type { RegionMetric } from "@/types";
import { formatCompactCurrency, formatInt, formatRatioAsPercent } from "@/utils/format";
import { cn } from "@/lib/utils";

export type MapMetric = "purchases" | "revenue" | "conversion" | "active_users";

/** Geometría estilizada: rectángulos redondeados por región, agrupados en macrorregiones. */
const REGION_SHAPES: Record<string, { x: number; y: number; w: number; h: number; group: "norte" | "centro" | "sur" | "oriente" }> = {
  Piura: { x: 10, y: 20, w: 46, h: 30, group: "norte" },
  "La Libertad": { x: 14, y: 54, w: 42, h: 28, group: "norte" },
  Lima: { x: 20, y: 120, w: 50, h: 34, group: "centro" },
  Junín: { x: 76, y: 108, w: 42, h: 30, group: "centro" },
  Ica: { x: 22, y: 158, w: 42, h: 28, group: "sur" },
  Arequipa: { x: 68, y: 168, w: 50, h: 34, group: "sur" },
  Cusco: { x: 96, y: 130, w: 46, h: 32, group: "oriente" },
  Puno: { x: 120, y: 168, w: 44, h: 32, group: "sur" },
  Tacna: { x: 92, y: 206, w: 40, h: 26, group: "sur" },
  Moquegua: { x: 62, y: 206, w: 40, h: 26, group: "sur" },
};

const GROUP_LABEL: Record<string, string> = {
  norte: "Norte",
  centro: "Centro",
  sur: "Sur",
  oriente: "Oriente",
};

const REGION_ALIASES: Record<string, string> = {
  LIMA: "Lima",
  AREQUIPA: "Arequipa",
  LA_LIBERTAD: "La Libertad",
  CUSCO: "Cusco",
  PIURA: "Piura",
  JUNIN: "Junín",
  PUNO: "Puno",
  ICA: "Ica",
  TACNA: "Tacna",
  MOQUEGUA: "Moquegua",
};

function regionLabel(region: string): string {
  return REGION_ALIASES[region.toUpperCase()] ?? region;
}

function valueFor(r: RegionMetric, metric: MapMetric): number {
  return r[metric];
}

function formatValue(value: number, metric: MapMetric): string {
  if (metric === "revenue") return formatCompactCurrency(value);
  if (metric === "conversion") return formatRatioAsPercent(value);
  return formatInt(value);
}

export function PeruMap({
  regions,
  metric,
  selected,
  onSelect,
}: {
  regions: RegionMetric[];
  metric: MapMetric;
  selected: string;
  onSelect: (region: string) => void;
}) {
  const [hover, setHover] = useState<string | null>(null);

  const normalizedRegions = regions.map((region) => ({ ...region, region: regionLabel(region.region) }));
  const withGeo = normalizedRegions.filter((r) => REGION_SHAPES[r.region]);
  const withoutGeo = normalizedRegions.filter((r) => !REGION_SHAPES[r.region]);

  const max = Math.max(1, ...normalizedRegions.map((r) => valueFor(r, metric)));
  const min = Math.min(0, ...normalizedRegions.map((r) => valueFor(r, metric)));

  const intensity = (r: RegionMetric) => {
    const v = valueFor(r, metric);
    return max === min ? 0.5 : (v - min) / (max - min);
  };

  const hoverRegion = useMemo(() => normalizedRegions.find((r) => r.region === hover) ?? null, [normalizedRegions, hover]);

  return (
    <div className="flex flex-col gap-3">
      <div className="relative">
        <svg
          viewBox="0 0 180 250"
          role="img"
          aria-label="Mapa coroplético simplificado del Perú por región"
          className="mx-auto h-[280px] w-full max-w-[220px]"
        >
          {withGeo.map((r) => {
            const shape = REGION_SHAPES[r.region];
            const t = intensity(r);
            const isSelected = selected === r.region;
            const isDimmed = selected !== "TODAS" && !isSelected;
            const fill = `color-mix(in oklab, var(--color-info) ${Math.round(t * 100)}%, var(--color-success) ${100 - Math.round(t * 100)}%)`;
            return (
              <g key={r.region}>
                <rect
                  x={shape.x}
                  y={shape.y}
                  width={shape.w}
                  height={shape.h}
                  rx={8}
                  fill={fill}
                  fillOpacity={isDimmed ? 0.28 : 0.92}
                  stroke={isSelected ? "var(--color-foreground)" : "var(--color-border)"}
                  strokeWidth={isSelected ? 2 : 1}
                  className="cursor-pointer transition-all"
                  onClick={() => onSelect(r.region)}
                  onMouseEnter={() => setHover(r.region)}
                  onMouseLeave={() => setHover((h) => (h === r.region ? null : h))}
                  tabIndex={0}
                  role="button"
                  aria-label={`${r.region}: ${formatValue(valueFor(r, metric), metric)}`}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") onSelect(r.region);
                  }}
                />
                <text
                  x={shape.x + shape.w / 2}
                  y={shape.y + shape.h / 2 + 3}
                  textAnchor="middle"
                  fontSize={7}
                  fill="var(--color-foreground)"
                  className="pointer-events-none select-none"
                >
                  {r.region.length > 9 ? `${r.region.slice(0, 8)}.` : r.region}
                </text>
              </g>
            );
          })}
        </svg>

        {hoverRegion && (
          <div
            className="pointer-events-none absolute left-1/2 top-1 -translate-x-1/2 rounded-md border border-panel-border bg-popover px-2.5 py-1.5 text-[11px] shadow-[var(--shadow-panel)]"
            role="status"
          >
            <p className="font-semibold text-foreground">{hoverRegion.region}</p>
            <p className="text-muted-foreground">{formatValue(valueFor(hoverRegion, metric), metric)}</p>
          </div>
        )}
      </div>

      {/* Leyenda de escala */}
      <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
        <span>Menor</span>
        <div
          className="h-2 flex-1 rounded-full"
          style={{
            background: "linear-gradient(to right, var(--color-success), var(--color-info))",
          }}
          aria-hidden
        />
        <span>Mayor</span>
      </div>

      {withoutGeo.length > 0 && (
        <div>
          <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Otras regiones
          </p>
          <ul className="flex flex-wrap gap-1.5">
            {withoutGeo.map((r) => {
              const isSelected = selected === r.region;
              return (
                <li key={r.region}>
                  <button
                    type="button"
                    onClick={() => onSelect(r.region)}
                    className={cn(
                      "rounded-md border border-panel-border px-2 py-1 text-[11px] transition-colors hover:bg-muted/40",
                      isSelected && "border-primary bg-primary/10 text-primary",
                    )}
                    aria-pressed={isSelected}
                  >
                    {r.region}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
