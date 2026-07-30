/**
 * websocketService
 * Conexión real al backend consumidor (FastAPI) mediante WebSocket o SSE,
 * con reconexión exponencial. Contrato de mensajes: ver src/types/index.ts.
 */
import { APP_CONFIG } from "./config";
import type { RealtimeConnection, MessageHandler } from "./mockRealtimeService";
import type { RealtimeMessage, Scenario } from "@/types";

type StatusHandler = (status: "CONECTADO" | "RECONECTANDO" | "DESCONECTADO") => void;

function parse(raw: string): RealtimeMessage | null {
  try {
    return JSON.parse(raw) as RealtimeMessage;
  } catch {
    return null;
  }
}

export function connectWebSocket(
  scenario: Scenario,
  onMessage: MessageHandler,
  onStatus: StatusHandler,
): RealtimeConnection {
  let socket: WebSocket | null = null;
  let attempts = 0;
  let closed = false;
  let currentScenario = scenario;
  let retryTimer: ReturnType<typeof setTimeout> | undefined;

  const open = () => {
    if (closed) return;
    onStatus(attempts === 0 ? "RECONECTANDO" : "RECONECTANDO");
    try {
      socket = new WebSocket(`${APP_CONFIG.websocketUrl}?scenario=${currentScenario}`);
    } catch {
      scheduleRetry();
      return;
    }
    socket.onopen = () => {
      attempts = 0;
      onStatus("CONECTADO");
    };
    socket.onmessage = (event) => {
      const message = parse(String(event.data));
      if (message) onMessage(message);
    };
    socket.onerror = () => onStatus("RECONECTANDO");
    socket.onclose = () => {
      if (closed) return;
      onStatus("DESCONECTADO");
      scheduleRetry();
    };
  };

  const scheduleRetry = () => {
    attempts += 1;
    const delay = Math.min(15000, 1000 * 2 ** Math.min(attempts, 4));
    retryTimer = setTimeout(open, delay);
  };

  open();

  return {
    disconnect: () => {
      closed = true;
      if (retryTimer) clearTimeout(retryTimer);
      socket?.close();
    },
    setScenario: (next: Scenario) => {
      currentScenario = next;
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ action: "set_scenario", scenario: next }));
      }
    },
  };
}

export function connectSse(
  scenario: Scenario,
  onMessage: MessageHandler,
  onStatus: StatusHandler,
): RealtimeConnection {
  let source: EventSource | null = null;
  let closed = false;
  let currentScenario = scenario;
  let attempts = 0;
  let retryTimer: ReturnType<typeof setTimeout> | undefined;

  const open = () => {
    if (closed) return;
    onStatus("RECONECTANDO");
    try {
      source = new EventSource(`${APP_CONFIG.sseUrl}?scenario=${currentScenario}`);
    } catch {
      scheduleRetry();
      return;
    }
    source.onopen = () => {
      attempts = 0;
      onStatus("CONECTADO");
    };
    source.onmessage = (event) => {
      const message = parse(String(event.data));
      if (message) onMessage(message);
    };
    source.onerror = () => {
      onStatus("DESCONECTADO");
      source?.close();
      scheduleRetry();
    };
  };

  const scheduleRetry = () => {
    attempts += 1;
    const delay = Math.min(15000, 1000 * 2 ** Math.min(attempts, 4));
    retryTimer = setTimeout(open, delay);
  };

  open();

  return {
    disconnect: () => {
      closed = true;
      if (retryTimer) clearTimeout(retryTimer);
      source?.close();
    },
    setScenario: (next: Scenario) => {
      currentScenario = next;
      source?.close();
      open();
    },
  };
}