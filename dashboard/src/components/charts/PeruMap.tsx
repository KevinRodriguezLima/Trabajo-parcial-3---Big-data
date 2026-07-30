/**
 * Mapa regional del Peru.
 *
 * No dibuja limites departamentales exactos; usa una silueta reconocible del
 * pais y ubica las regiones como burbujas segun su posicion aproximada.
 */
import { useMemo, useState } from "react";
import type { RegionMetric } from "@/types";
import { formatCompactCurrency, formatInt, formatRatioAsPercent } from "@/utils/format";
import { cn } from "@/lib/utils";

export type MapMetric = "purchases" | "revenue" | "conversion" | "active_users";

const PERU_OUTLINE =
  "M78 9 L69 21 L64 36 L58 49 L54 66 L46 82 L40 101 L33 119 L35 136 L44 151 L47 168 L53 184 L58 201 L66 218 L78 239 L91 247 L98 234 L108 219 L123 205 L136 190 L148 173 L156 155 L160 137 L154 119 L146 101 L140 83 L137 64 L133 46 L122 32 L108 26 L94 18 L84 8 Z";

const COASTLINE =
  "M78 9 L69 21 L64 36 L58 49 L54 66 L46 82 L40 101 L33 119 L35 136 L44 151 L47 168 L53 184 L58 201 L66 218 L78 239";

const REGION_POINTS: Record<string, { x: number; y: number; labelDx?: number; labelDy?: number }> =
  {
    Piura: { x: 55, y: 34, labelDx: -30 },
    "La Libertad": { x: 57, y: 75, labelDx: -38 },
    Lima: { x: 61, y: 126, labelDx: -28 },
    Junin: { x: 87, y: 113, labelDx: 14 },
    Junín: { x: 87, y: 113, labelDx: 14 },
    Ica: { x: 65, y: 158, labelDx: -24 },
    Arequipa: { x: 91, y: 190, labelDx: -46, labelDy: 14 },
    Cusco: { x: 111, y: 146, labelDx: 15 },
    Puno: { x: 133, y: 183, labelDx: 15 },
    Moquegua: { x: 103, y: 214, labelDx: -48, labelDy: 12 },
    Tacna: { x: 109, y: 231, labelDx: 15, labelDy: 6 },
  };

const REGION_ALIASES: Record<string, string> = {
  LIMA: "Lima",
  AREQUIPA: "Arequipa",
  LA_LIBERTAD: "La Libertad",
  CUSCO: "Cusco",
  PIURA: "Piura",
  JUNIN: "Junin",
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

  const normalizedRegions = useMemo(
    () => regions.map((region) => ({ ...region, region: regionLabel(region.region) })),
    [regions],
  );
  const placedRegions = normalizedRegions.filter((r) => REGION_POINTS[r.region]);
  const unplacedRegions = normalizedRegions.filter((r) => !REGION_POINTS[r.region]);
  const max = Math.max(1, ...normalizedRegions.map((r) => valueFor(r, metric)));
  const min = Math.min(0, ...normalizedRegions.map((r) => valueFor(r, metric)));

  const intensity = (r: RegionMetric) => {
    const value = valueFor(r, metric);
    return max === min ? 0.5 : (value - min) / (max - min);
  };

  const hoverRegion = useMemo(
    () => normalizedRegions.find((r) => r.region === hover) ?? null,
    [normalizedRegions, hover],
  );

  return (
    <div className="flex flex-col gap-3">
      <div className="relative rounded-lg border border-panel-border bg-muted/10 px-3 py-2">
        <svg
          viewBox="0 0 190 260"
          role="img"
          aria-label="Mapa regional del Peru con burbujas por region"
          className="mx-auto h-[320px] w-full max-w-[260px]"
        >
          <defs>
            <linearGradient id="peru-land" x1="0" x2="1" y1="0" y2="1">
              <stop offset="0%" stopColor="var(--color-muted)" stopOpacity="0.45" />
              <stop offset="100%" stopColor="var(--color-muted)" stopOpacity="0.12" />
            </linearGradient>
          </defs>

          <path
            d={PERU_OUTLINE}
            fill="url(#peru-land)"
            stroke="var(--color-border)"
            strokeWidth={1.4}
          />
          <path
            d={COASTLINE}
            fill="none"
            stroke="var(--color-info)"
            strokeWidth={2.2}
            strokeLinecap="round"
          />

          {placedRegions.map((r) => {
            const point = REGION_POINTS[r.region];
            const t = intensity(r);
            const radius = 5 + t * 12;
            const isSelected = selected === r.region;
            const isDimmed = selected !== "TODAS" && !isSelected;
            const fill = `color-mix(in oklab, var(--color-success) ${Math.round(35 + t * 45)}%, var(--color-info))`;
            const labelX = point.x + (point.labelDx ?? 13);
            const labelY = point.y + (point.labelDy ?? 0);

            return (
              <g key={r.region}>
                <line
                  x1={point.x}
                  y1={point.y}
                  x2={labelX}
                  y2={labelY}
                  stroke="var(--color-border)"
                  strokeOpacity={isDimmed ? 0.2 : 0.55}
                  strokeWidth={0.8}
                />
                <circle
                  cx={point.x}
                  cy={point.y}
                  r={radius}
                  fill={fill}
                  fillOpacity={isDimmed ? 0.24 : 0.88}
                  stroke={isSelected ? "var(--color-foreground)" : "var(--color-background)"}
                  strokeWidth={isSelected ? 2.5 : 1.4}
                  className="cursor-pointer transition-opacity"
                  onClick={() => onSelect(r.region)}
                  onMouseEnter={() => setHover(r.region)}
                  onMouseLeave={() =>
                    setHover((current) => (current === r.region ? null : current))
                  }
                  tabIndex={0}
                  role="button"
                  aria-label={`${r.region}: ${formatValue(valueFor(r, metric), metric)}`}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") onSelect(r.region);
                  }}
                />
                <text
                  x={labelX}
                  y={labelY + 3}
                  textAnchor={labelX < point.x ? "end" : "start"}
                  fontSize={8}
                  fontWeight={isSelected ? 700 : 500}
                  fill="var(--color-foreground)"
                  opacity={isDimmed ? 0.38 : 0.9}
                  className="pointer-events-none select-none"
                >
                  {r.region}
                </text>
              </g>
            );
          })}
        </svg>

        {hoverRegion && (
          <div
            className="pointer-events-none absolute left-1/2 top-3 -translate-x-1/2 rounded-md border border-panel-border bg-popover px-2.5 py-1.5 text-[11px] shadow-[var(--shadow-panel)]"
            role="status"
          >
            <p className="font-semibold text-foreground">{hoverRegion.region}</p>
            <p className="text-muted-foreground">
              {formatValue(valueFor(hoverRegion, metric), metric)}
            </p>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
        <span>Menor</span>
        <div
          className="h-2 flex-1 rounded-full"
          style={{
            background: "linear-gradient(to right, var(--color-info), var(--color-success))",
          }}
          aria-hidden
        />
        <span>Mayor</span>
      </div>

      {unplacedRegions.length > 0 && (
        <div>
          <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Otras regiones
          </p>
          <ul className="flex flex-wrap gap-1.5">
            {unplacedRegions.map((r) => {
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
