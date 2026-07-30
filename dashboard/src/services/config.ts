/**
 * Configuración central de conexión.
 * Variables soportadas (archivo .env):
 *   VITE_DATA_MODE=mock | websocket | sse
 *   VITE_WEBSOCKET_URL=ws://localhost:8000/ws/dashboard
 *   VITE_SSE_URL=http://localhost:8000/events/dashboard
 */
import type { DataMode } from "@/types";

const env = import.meta.env as Record<string, string | undefined>;

export const APP_CONFIG = {
  appName: "AudienceStream",
  fullTitle: "Dashboard de Audiencias Digitales en Tiempo Real",
  course: "BIGDATA 2026A",
  version: "1.0.0",
  defaultMode: (env.VITE_DATA_MODE as DataMode) || "mock",
  websocketUrl: env.VITE_WEBSOCKET_URL || "ws://localhost:8000/ws/dashboard",
  sseUrl: env.VITE_SSE_URL || "http://localhost:8000/events/dashboard",
  snapshotUrl: env.VITE_API_URL || "http://localhost:8000/api/dashboard/snapshot",
  tickIntervalMs: 1500,
  maxSeriesPoints: 5000,
} as const;

export const MODE_LABEL: Record<DataMode, string> = {
  mock: "Modo demostración",
  websocket: "WebSocket real",
  sse: "Server-Sent Events",
};
