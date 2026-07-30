/**
 * Mapa regional del Perú basado en geometría GeoJSON real.
 *
 * - Dibuja los límites departamentales.
 * - Calcula automáticamente la posición de cada burbuja.
 * - Normaliza nombres como JUNIN, Junín, LA_LIBERTAD, etc.
 * - Adapta el mapa al espacio disponible sin scroll.
 */

import { useMemo, useState } from "react";
import { geoMercator, geoPath } from "d3-geo";
import type {
  Feature,
  FeatureCollection,
  Geometry,
  GeoJsonProperties,
} from "geojson";

import peruDepartmentsJson from "@/data/peru-departments.json";

import type { RegionMetric } from "@/types";
import {
  formatCompactCurrency,
  formatInt,
  formatRatioAsPercent,
} from "@/utils/format";
import { cn } from "@/lib/utils";

export type MapMetric =
  | "purchases"
  | "revenue"
  | "conversion"
  | "active_users";

const MAP_WIDTH = 520;
const MAP_HEIGHT = 650;

const peruDepartments =
  peruDepartmentsJson as FeatureCollection<Geometry, GeoJsonProperties>;

/**
 * Nombres visuales para conservar tildes y formato.
 */
const DISPLAY_NAMES: Record<string, string> = {
  AMAZONAS: "Amazonas",
  ANCASH: "Áncash",
  APURIMAC: "Apurímac",
  AREQUIPA: "Arequipa",
  AYACUCHO: "Ayacucho",
  CAJAMARCA: "Cajamarca",
  CALLAO: "Callao",
  CUSCO: "Cusco",
  HUANCAVELICA: "Huancavelica",
  HUANUCO: "Huánuco",
  ICA: "Ica",
  JUNIN: "Junín",
  LA_LIBERTAD: "La Libertad",
  LAMBAYEQUE: "Lambayeque",
  LIMA: "Lima",
  LORETO: "Loreto",
  MADRE_DE_DIOS: "Madre de Dios",
  MOQUEGUA: "Moquegua",
  PASCO: "Pasco",
  PIURA: "Piura",
  PUNO: "Puno",
  SAN_MARTIN: "San Martín",
  TACNA: "Tacna",
  TUMBES: "Tumbes",
  UCAYALI: "Ucayali",
};

/**
 * Ajustes visuales para evitar que algunas etiquetas se superpongan.
 */
const LABEL_OFFSETS: Record<string, { dx: number; dy: number }> = {
  PIURA: { dx: -42, dy: 0 },
  LA_LIBERTAD: { dx: -55, dy: 0 },
  LIMA: { dx: -42, dy: 4 },
  CALLAO: { dx: -48, dy: -12 },
  ICA: { dx: -35, dy: 8 },
  AREQUIPA: { dx: -58, dy: 18 },
  JUNIN: { dx: 30, dy: -6 },
  CUSCO: { dx: 34, dy: 4 },
  PUNO: { dx: 34, dy: 6 },
  MOQUEGUA: { dx: -54, dy: 14 },
  TACNA: { dx: 32, dy: 14 },
};

/**
 * Convierte:
 *
 * "Junín"       -> "JUNIN"
 * "LA_LIBERTAD" -> "LA_LIBERTAD"
 * "La Libertad" -> "LA_LIBERTAD"
 */
function normalizeRegionKey(value: string): string {
  return value
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .replace(/[\s-]+/g, "_")
    .replace(/_+/g, "_")
    .trim()
    .toUpperCase();
}

function regionLabel(value: string): string {
  const key = normalizeRegionKey(value);
  return DISPLAY_NAMES[key] ?? value.replaceAll("_", " ");
}

/**
 * Diferentes GeoJSON utilizan diferentes nombres para la propiedad
 * del departamento.
 */
function getDepartmentName(
  feature: Feature<Geometry, GeoJsonProperties>,
): string {
  const properties = feature.properties ?? {};

  const possibleKeys = [
    "NOMBDEP",
    "NOMB_DEPA",
    "DEPARTAMEN",
    "DEPARTAMENTO",
    "departamento",
    "NAME_1",
    "name",
    "NAME",
    "NOMBRE",
  ];

  for (const key of possibleKeys) {
    const value = properties[key];

    if (typeof value === "string" && value.trim()) {
      return value;
    }
  }

  return "";
}

function valueFor(region: RegionMetric, metric: MapMetric): number {
  return region[metric];
}

function formatValue(value: number, metric: MapMetric): string {
  if (metric === "revenue") {
    return formatCompactCurrency(value);
  }

  if (metric === "conversion") {
    return formatRatioAsPercent(value);
  }

  return formatInt(value);
}

function intensityColor(intensity: number): string {
  const infoPercentage = Math.round((1 - intensity) * 100);
  const successPercentage = Math.round(intensity * 100);

  return `color-mix(
    in oklab,
    var(--color-info) ${infoPercentage}%,
    var(--color-success) ${successPercentage}%
  )`;
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
  const [hoveredKey, setHoveredKey] = useState<string | null>(null);

  /**
   * Ajusta automáticamente el mapa al viewBox.
   */
  const projection = useMemo(() => {
    return geoMercator().fitExtent(
      [
        [30, 25],
        [MAP_WIDTH - 30, MAP_HEIGHT - 25],
      ],
      peruDepartments,
    );
  }, []);

  const pathGenerator = useMemo(
    () => geoPath(projection),
    [projection],
  );

  /**
   * Normalización de los datos recibidos desde el backend.
   */
  const normalizedRegions = useMemo(
    () =>
      regions.map((region) => ({
        ...region,
        region: regionLabel(region.region),
        regionKey: normalizeRegionKey(region.region),
      })),
    [regions],
  );

  const regionsByKey = useMemo(
    () =>
      new Map(
        normalizedRegions.map((region) => [
          region.regionKey,
          region,
        ]),
      ),
    [normalizedRegions],
  );

  const departmentFeatures = useMemo(
    () =>
      peruDepartments.features
        .map((feature) => {
          const rawName = getDepartmentName(feature);
          const key = normalizeRegionKey(rawName);

          return {
            feature,
            key,
            name: regionLabel(rawName),
          };
        })
        .filter((department) => department.key),
    [],
  );

  const departmentKeys = useMemo(
    () => new Set(departmentFeatures.map((department) => department.key)),
    [departmentFeatures],
  );

  const unplacedRegions = useMemo(
    () =>
      normalizedRegions.filter(
        (region) => !departmentKeys.has(region.regionKey),
      ),
    [normalizedRegions, departmentKeys],
  );

  /**
   * Antes se utilizaba Math.min(0, ...values), lo cual obligaba a que
   * el mínimo fuera cero aunque todas las regiones tuvieran valores positivos.
   */
  const { minValue, maxValue } = useMemo(() => {
    const values = normalizedRegions.map((region) =>
      valueFor(region, metric),
    );

    if (values.length === 0) {
      return {
        minValue: 0,
        maxValue: 1,
      };
    }

    return {
      minValue: Math.min(...values),
      maxValue: Math.max(...values),
    };
  }, [normalizedRegions, metric]);

  function getIntensity(value: number): number {
    if (maxValue === minValue) {
      return 0.5;
    }

    return (value - minValue) / (maxValue - minValue);
  }

  const selectedKey = normalizeRegionKey(selected);
  const allRegionsSelected = selectedKey === "TODAS";

  const hoveredRegion = hoveredKey
    ? regionsByKey.get(hoveredKey) ?? null
    : null;

  return (
    <div className="flex min-h-0 flex-col gap-3">
      <div className="relative min-h-0 flex-1 overflow-hidden rounded-lg border border-panel-border bg-muted/10">
        <svg
          viewBox={`0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`}
          role="img"
          aria-label="Mapa departamental del Perú con métricas regionales"
          preserveAspectRatio="xMidYMid meet"
          className="mx-auto block h-full max-h-[540px] min-h-[340px] w-full"
        >
          <defs>
            <filter
              id="bubble-shadow"
              x="-30%"
              y="-30%"
              width="160%"
              height="160%"
            >
              <feDropShadow
                dx="0"
                dy="2"
                stdDeviation="2"
                floodColor="black"
                floodOpacity="0.35"
              />
            </filter>
          </defs>

          {/* Límites departamentales reales */}
          <g>
            {departmentFeatures.map(({ feature, key, name }) => {
              const region = regionsByKey.get(key);
              const hasData = Boolean(region);

              const isSelected = selectedKey === key;
              const isDimmed =
                !allRegionsSelected && !isSelected;

              const value = region
                ? valueFor(region, metric)
                : 0;

              const intensity = region
                ? getIntensity(value)
                : 0;

              const fill = hasData
                ? intensityColor(intensity)
                : "var(--color-muted)";

              return (
                <path
                  key={`department-${key}`}
                  d={pathGenerator(feature) ?? undefined}
                  fill={fill}
                  fillOpacity={
                    !hasData
                      ? 0.12
                      : isDimmed
                        ? 0.16
                        : 0.34
                  }
                  stroke="var(--color-border)"
                  strokeWidth={1}
                  vectorEffect="non-scaling-stroke"
                  className={cn(
                    "transition-all duration-200",
                    hasData && "cursor-pointer",
                  )}
                  onClick={() => {
                    if (region) {
                      onSelect(region.region);
                    }
                  }}
                  onMouseEnter={() => {
                    if (region) {
                      setHoveredKey(key);
                    }
                  }}
                  onMouseLeave={() => {
                    setHoveredKey((current) =>
                      current === key ? null : current,
                    );
                  }}
                  tabIndex={hasData ? 0 : -1}
                  role={hasData ? "button" : undefined}
                  aria-label={
                    region
                      ? `${name}: ${formatValue(value, metric)}`
                      : name
                  }
                  onKeyDown={(event) => {
                    if (
                      region &&
                      (event.key === "Enter" ||
                        event.key === " ")
                    ) {
                      event.preventDefault();
                      onSelect(region.region);
                    }
                  }}
                />
              );
            })}
          </g>

          {/* Burbujas calculadas desde los centroides departamentales */}
          <g>
            {departmentFeatures.map(({ feature, key }) => {
              const region = regionsByKey.get(key);

              if (!region) {
                return null;
              }

              const [centerX, centerY] =
                pathGenerator.centroid(feature);

              if (
                !Number.isFinite(centerX) ||
                !Number.isFinite(centerY)
              ) {
                return null;
              }

              const value = valueFor(region, metric);
              const intensity = getIntensity(value);

              /**
               * La raíz cuadrada evita que la región con mayor valor
               * produzca una burbuja desproporcionadamente grande.
               */
              const radius = 7 + Math.sqrt(intensity) * 19;

              const isSelected = selectedKey === key;
              const isDimmed =
                !allRegionsSelected && !isSelected;

              const offset = LABEL_OFFSETS[key] ?? {
                dx: 28,
                dy: 0,
              };

              const labelX = centerX + offset.dx;
              const labelY = centerY + offset.dy;

              const textAnchor =
                offset.dx < 0 ? "end" : "start";

              return (
                <g
                  key={`bubble-${key}`}
                  opacity={isDimmed ? 0.28 : 1}
                  className="transition-opacity duration-200"
                >
                  <line
                    x1={centerX}
                    y1={centerY}
                    x2={labelX}
                    y2={labelY}
                    stroke="var(--color-border)"
                    strokeWidth={1}
                    strokeOpacity={0.75}
                    vectorEffect="non-scaling-stroke"
                  />

                  <circle
                    cx={centerX}
                    cy={centerY}
                    r={radius}
                    fill={intensityColor(intensity)}
                    fillOpacity={0.92}
                    stroke={
                      isSelected
                        ? "var(--color-foreground)"
                        : "var(--color-background)"
                    }
                    strokeWidth={isSelected ? 4 : 2}
                    filter="url(#bubble-shadow)"
                    className="cursor-pointer transition-all duration-200 hover:brightness-110"
                    onClick={() => onSelect(region.region)}
                    onMouseEnter={() => setHoveredKey(key)}
                    onMouseLeave={() =>
                      setHoveredKey((current) =>
                        current === key ? null : current,
                      )
                    }
                  >
                    <title>
                      {region.region}:{" "}
                      {formatValue(value, metric)}
                    </title>
                  </circle>

                  <text
                    x={labelX}
                    y={labelY + 4}
                    textAnchor={textAnchor}
                    fontSize={13}
                    fontWeight={isSelected ? 700 : 600}
                    fill="var(--color-foreground)"
                    className="pointer-events-none select-none"
                  >
                    {region.region}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>

        {hoveredRegion && (
          <div
            className="pointer-events-none absolute left-1/2 top-3 z-10 -translate-x-1/2 rounded-md border border-panel-border bg-popover px-3 py-2 text-xs shadow-[var(--shadow-panel)]"
            role="status"
          >
            <p className="font-semibold text-foreground">
              {hoveredRegion.region}
            </p>

            <p className="text-muted-foreground">
              {formatValue(
                valueFor(hoveredRegion, metric),
                metric,
              )}
            </p>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
        <span>Menor</span>

        <div
          className="h-2 flex-1 rounded-full"
          style={{
            background:
              "linear-gradient(to right, var(--color-info), var(--color-success))",
          }}
          aria-hidden
        />

        <span>Mayor</span>
      </div>

      {unplacedRegions.length > 0 && (
        <div>
          <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Regiones no encontradas en el mapa
          </p>

          <ul className="flex flex-wrap gap-1.5">
            {unplacedRegions.map((region) => {
              const isSelected =
                selectedKey === region.regionKey;

              return (
                <li key={region.regionKey}>
                  <button
                    type="button"
                    onClick={() => onSelect(region.region)}
                    className={cn(
                      "rounded-md border border-panel-border px-2 py-1 text-[11px] transition-colors hover:bg-muted/40",
                      isSelected &&
                        "border-primary bg-primary/10 text-primary",
                    )}
                    aria-pressed={isSelected}
                  >
                    {region.region}
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