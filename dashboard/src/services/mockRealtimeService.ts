/**
 * mockRealtimeService
 * Emula el flujo Kafka → Flink → Backend → WebSocket generando mensajes
 * `RealtimeMessage` a intervalos regulares con datos coherentes.
 */
import { APP_CONFIG } from "./config";
import { ScenarioEngine } from "./metricsService";
import type { RealtimeMessage, Scenario } from "@/types";

export type MessageHandler = (message: RealtimeMessage) => void;

export interface RealtimeConnection {
  disconnect: () => void;
  setScenario: (scenario: Scenario) => void;
  acknowledgeAlert?: (id: string) => void;
  resolveAlert?: (id: string) => void;
}

export function connectMockRealtime(
  scenario: Scenario,
  onMessage: MessageHandler,
): RealtimeConnection {
  let engine = new ScenarioEngine(scenario);
  let stopped = false;

  const emitSnapshot = () => {
    const { snapshot, newAlert } = engine.next();
    onMessage({
      message_type: "dashboard_update",
      timestamp: snapshot.timestamp,
      scenario: engine.scenario,
      metrics: snapshot.metrics,
      snapshot,
    });
    if (newAlert) {
      onMessage({
        message_type: "alert_created",
        timestamp: newAlert.timestamp,
        scenario: engine.scenario,
        alert: newAlert,
      });
    }
  };

  // Primer snapshot inmediato para evitar pantallas vacías.
  emitSnapshot();
  const interval = setInterval(() => {
    if (stopped) return;
    emitSnapshot();
  }, APP_CONFIG.tickIntervalMs);

  const heartbeat = setInterval(() => {
    if (stopped) return;
    onMessage({
      message_type: "heartbeat",
      timestamp: new Date().toISOString(),
      scenario: engine.scenario,
    });
  }, 10000);

  return {
    disconnect: () => {
      stopped = true;
      clearInterval(interval);
      clearInterval(heartbeat);
    },
    setScenario: (next: Scenario) => {
      engine = new ScenarioEngine(next);
      onMessage({
        message_type: "scenario_changed",
        timestamp: new Date().toISOString(),
        scenario: next,
      });
      emitSnapshot();
    },
    acknowledgeAlert: (id: string) => {
      engine.acknowledge(id);
      emitSnapshot();
    },
    resolveAlert: (id: string) => {
      engine.resolve(id);
      emitSnapshot();
    },
  };
}