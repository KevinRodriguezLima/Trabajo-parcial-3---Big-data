/**
 * useRealtimeDashboard
 * Hook + proveedor central del dashboard: gestiona la conexión (mock, WebSocket
 * o SSE), la reconexión, el historial temporal, la pausa de actualizaciones,
 * los filtros globales y los errores.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { toast } from "sonner";
import { APP_CONFIG, MODE_LABEL } from "@/services/config";
import { connectMockRealtime, type RealtimeConnection } from "@/services/mockRealtimeService";
import { connectSse, connectWebSocket } from "@/services/websocketService";
import type {
  ConnectionStatus,
  DashboardMetrics,
  DataMode,
  GlobalFilters,
  RealtimeMessage,
  Scenario,
  ThroughputPoint,
} from "@/types";
import { formatTime } from "@/utils/format";

export const DEFAULT_FILTERS: GlobalFilters = {
  scenario: "BASE",
  timeRange: "5m",
  region: "TODAS",
  profile: "TODOS",
  eventType: "TODOS",
  source: "TODOS",
  alertLevel: "TODOS",
  audience: "TODAS",
  product: "TODOS",
  funnelStage: "TODAS",
  window: null,
};

interface DashboardContextValue {
  snapshot: DashboardMetrics | null;
  throughput: ThroughputPoint[];
  status: ConnectionStatus;
  mode: DataMode;
  paused: boolean;
  loading: boolean;
  error: string | null;
  lastUpdate: string | null;
  filters: GlobalFilters;
  setMode: (mode: DataMode) => void;
  setScenario: (scenario: Scenario) => void;
  setFilters: (patch: Partial<GlobalFilters>) => void;
  resetFilters: () => void;
  togglePause: () => void;
  refresh: () => void;
  acknowledgeAlert: (id: string) => void;
  resolveAlert: (id: string) => void;
}

const DashboardContext = createContext<DashboardContextValue | null>(null);

export function DashboardProvider({ children }: { children: ReactNode }) {
  const [snapshot, setSnapshot] = useState<DashboardMetrics | null>(null);
  const [throughput, setThroughput] = useState<ThroughputPoint[]>([]);
  const [status, setStatus] = useState<ConnectionStatus>("RECONECTANDO");
  const [mode, setModeState] = useState<DataMode>(APP_CONFIG.defaultMode);
  const [paused, setPaused] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);
  const [filters, setFiltersState] = useState<GlobalFilters>(DEFAULT_FILTERS);
  const [ackIds, setAckIds] = useState<Record<string, "RECONOCIDA" | "RESUELTA">>({});

  const connectionRef = useRef<RealtimeConnection | null>(null);
  const pausedRef = useRef(paused);
  pausedRef.current = paused;

  const handleMessage = useCallback((message: RealtimeMessage) => {
    if (pausedRef.current && message.message_type !== "error") return;
    switch (message.message_type) {
      case "dashboard_update":
        if (message.snapshot) {
          setSnapshot(message.snapshot);
          setThroughput((prev) => {
            const point: ThroughputPoint = {
              timestamp: Date.now(),
              label: formatTime(new Date()),
              eps: message.snapshot!.metrics.events_per_second,
              purchases: message.snapshot!.metrics.total_purchases,
            };
            const next = [...prev, point];
            return next.length > APP_CONFIG.maxSeriesPoints
              ? next.slice(next.length - APP_CONFIG.maxSeriesPoints)
              : next;
          });
          setLastUpdate(message.snapshot.timestamp);
          setError(null);
        }
        break;
      case "alert_created":
        if (message.alert?.level === "CRITICAL") {
          toast.error(message.alert.title, { description: message.alert.description });
        }
        break;
      case "error":
        setError(message.error ?? "Error desconocido del backend");
        break;
      default:
        break;
    }
  }, []);

  // Establece la conexión según el modo seleccionado.
  useEffect(() => {
    connectionRef.current?.disconnect();
    setSnapshot(null);
    setThroughput([]);
    setError(null);

    if (mode === "mock") {
      setStatus("DEMO");
      connectionRef.current = connectMockRealtime(filters.scenario, handleMessage);
    } else {
      setStatus("RECONECTANDO");
      const onStatus = (s: "CONECTADO" | "RECONECTANDO" | "DESCONECTADO") => setStatus(s);
      connectionRef.current =
        mode === "websocket"
          ? connectWebSocket(filters.scenario, handleMessage, onStatus)
          : connectSse(filters.scenario, handleMessage, onStatus);
    }

    return () => connectionRef.current?.disconnect();
    // Reconectar solo al cambiar de modo; el escenario se propaga por setScenario.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, handleMessage]);

  const setScenario = useCallback((scenario: Scenario) => {
    setFiltersState((prev) => ({ ...prev, scenario }));
    setThroughput([]);
    setAckIds({});
    connectionRef.current?.setScenario(scenario);
  }, []);

  const setMode = useCallback((next: DataMode) => {
    setModeState(next);
    toast.info(`Origen de datos: ${MODE_LABEL[next]}`, {
      description:
        next === "mock"
          ? "Los datos se generan localmente para la demostración académica."
          : `Intentando conectar con ${next === "websocket" ? APP_CONFIG.websocketUrl : APP_CONFIG.sseUrl}`,
    });
  }, []);

  const value = useMemo<DashboardContextValue>(() => {
    const decorated = snapshot
      ? {
          ...snapshot,
          alerts: snapshot.alerts.map((a) => (ackIds[a.id] ? { ...a, status: ackIds[a.id] } : a)),
        }
      : null;
    return {
      snapshot: decorated,
      throughput,
      status,
      mode,
      paused,
      loading: !snapshot,
      error,
      lastUpdate,
      filters,
      setMode,
      setScenario,
      setFilters: (patch) => setFiltersState((prev) => ({ ...prev, ...patch })),
      resetFilters: () =>
        setFiltersState((prev) => ({ ...DEFAULT_FILTERS, scenario: prev.scenario })),
      togglePause: () =>
        setPaused((p) => {
          toast.info(p ? "Actualización reanudada" : "Actualización pausada");
          return !p;
        }),
      refresh: () => {
        connectionRef.current?.setScenario(filters.scenario);
        toast.success("Datos actualizados");
      },
      acknowledgeAlert: (id) => {
        setAckIds((prev) => ({ ...prev, [id]: "RECONOCIDA" }));
        connectionRef.current?.acknowledgeAlert?.(id);
        toast.success("Alerta marcada como reconocida");
      },
      resolveAlert: (id) => {
        setAckIds((prev) => ({ ...prev, [id]: "RESUELTA" }));
        connectionRef.current?.resolveAlert?.(id);
        toast.success("Alerta marcada como resuelta");
      },
    };
  }, [snapshot, throughput, status, mode, paused, error, lastUpdate, filters, ackIds, setMode, setScenario]);

  return <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>;
}

export function useRealtimeDashboard(): DashboardContextValue {
  const ctx = useContext(DashboardContext);
  if (!ctx) throw new Error("useRealtimeDashboard debe usarse dentro de DashboardProvider");
  return ctx;
}