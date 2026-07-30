/** Utilidades de formato para presentación en español (Perú). */

const numberFormatter = new Intl.NumberFormat("es-PE");

export function formatNumber(value: number, decimals = 0): string {
  return new Intl.NumberFormat("es-PE", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

export function formatInt(value: number): string {
  return numberFormatter.format(Math.round(value));
}

export function formatCurrency(value: number): string {
  return `S/ ${new Intl.NumberFormat("es-PE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)}`;
}

export function formatCompactCurrency(value: number): string {
  if (value >= 1_000_000) return `S/ ${(value / 1_000_000).toFixed(2)} M`;
  if (value >= 1_000) return `S/ ${(value / 1_000).toFixed(1)} k`;
  return formatCurrency(value);
}

export function formatPercent(value: number, decimals = 2): string {
  return `${new Intl.NumberFormat("es-PE", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value)} %`;
}

export function formatRatioAsPercent(ratio: number, decimals = 2): string {
  return formatPercent(ratio * 100, decimals);
}

export function formatEps(value: number): string {
  return `${value.toFixed(1)} eps`;
}

export function formatDelta(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)} %`;
}

export function formatTime(date: Date | string): string {
  const d = typeof date === "string" ? new Date(date) : date;
  return d.toLocaleTimeString("es-PE", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

export function formatDateTime(date: Date | string): string {
  const d = typeof date === "string" ? new Date(date) : date;
  return d.toLocaleString("es-PE", {
    day: "2-digit",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function relativeTime(date: Date | string): string {
  const d = typeof date === "string" ? new Date(date) : date;
  const diff = Math.max(0, Date.now() - d.getTime());
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return `hace ${seconds} s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `hace ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `hace ${hours} h`;
  return `hace ${Math.floor(hours / 24)} d`;
}

export function toCsv(rows: Array<Record<string, string | number>>): string {
  if (rows.length === 0) return "";
  const headers = Object.keys(rows[0]);
  const escape = (v: string | number) => {
    const s = String(v);
    return /[",;\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [
    headers.join(";"),
    ...rows.map((row) => headers.map((h) => escape(row[h])).join(";")),
  ].join("\n");
}

export function downloadFile(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}