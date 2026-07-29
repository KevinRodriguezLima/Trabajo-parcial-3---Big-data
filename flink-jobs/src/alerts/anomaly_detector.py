from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional
from ..config import CONFIG, AnomalyConfig

class AnomalyDetector:
    """
    Detector de anomalías y alertas en tiempo real sobre el flujo de eventos.
    """
    def __init__(self, config: Optional[AnomalyConfig] = None):
        self.config = config or CONFIG.anomalies
        self.moving_average_eps = 50.0  # baseline por defecto

    def update_baseline_eps(self, eps: float):
        """Actualiza la media móvil exponencial de eventos/segundo."""
        alpha = 0.1
        self.moving_average_eps = alpha * eps + (1 - alpha) * self.moving_average_eps

    def detect(self, events: List[Dict[str, Any]], window_start: str, window_end: str) -> List[Dict[str, Any]]:
        alerts = []
        now_str = datetime.now(timezone.utc).isoformat()

        if not events:
            return alerts

        # 1. Chequeo de Spike o Caída de Tráfico
        total_events = len(events)
        duration_sec = 10.0
        current_eps = total_events / duration_sec

        if current_eps > self.config.spike_multiplier * self.moving_average_eps and total_events > 20:
            alerts.append({
                "alert_id": f"ALT_SPIKE_{uuid.uuid4().hex[:8]}",
                "alert_type": "TRAFFIC_SPIKE",
                "severity": "WARNING",
                "message": f"Spike de tráfico detectado: {round(current_eps, 1)} ev/s (Media esperada: {round(self.moving_average_eps, 1)} ev/s)",
                "current_value": round(current_eps, 2),
                "threshold_value": round(self.config.spike_multiplier * self.moving_average_eps, 2),
                "window_start": window_start,
                "window_end": window_end,
                "detected_at": now_str
            })
        elif current_eps < self.config.drop_multiplier * self.moving_average_eps and self.moving_average_eps > 10.0:
            alerts.append({
                "alert_id": f"ALT_DROP_{uuid.uuid4().hex[:8]}",
                "alert_type": "TRAFFIC_DROP",
                "severity": "CRITICAL",
                "message": f"Caída drástica de tráfico: {round(current_eps, 1)} ev/s (Media esperada: {round(self.moving_average_eps, 1)} ev/s)",
                "current_value": round(current_eps, 2),
                "threshold_value": round(self.config.drop_multiplier * self.moving_average_eps, 2),
                "window_start": window_start,
                "window_end": window_end,
                "detected_at": now_str
            })

        self.update_baseline_eps(current_eps)

        # 2. Chequeo de Tasa de Fallo de Pagos
        purchases = sum(1 for e in events if e.get("event_type") == "PURCHASE")
        payment_fails = sum(1 for e in events if e.get("event_type") == "PAYMENT_FAILED")
        total_attempts = purchases + payment_fails

        if total_attempts >= 5:
            fail_pct = (payment_fails / float(total_attempts)) * 100.0
            if fail_pct >= self.config.payment_fail_threshold_pct:
                alerts.append({
                    "alert_id": f"ALT_PAYMENT_{uuid.uuid4().hex[:8]}",
                    "alert_type": "HIGH_PAYMENT_FAILURE_RATE",
                    "severity": "CRITICAL",
                    "message": f"Tasa de fallos en pasarela de pago inusualmente alta: {round(fail_pct, 1)}%",
                    "current_value": round(fail_pct, 2),
                    "threshold_value": self.config.payment_fail_threshold_pct,
                    "window_start": window_start,
                    "window_end": window_end,
                    "detected_at": now_str
                })

        # 3. Chequeo de Carritos de Alto Valor (Spam o Compras Masivas)
        for e in events:
            if e.get("event_type") in ("ADD_TO_CART", "PURCHASE"):
                cart_val = float(e.get("payload", {}).get("cart_value_after", e.get("payload", {}).get("total_amount", 0.0)))
                if cart_val >= self.config.high_cart_threshold:
                    alerts.append({
                        "alert_id": f"ALT_CART_{uuid.uuid4().hex[:8]}",
                        "alert_type": "HIGH_VALUE_CART",
                        "severity": "WARNING",
                        "message": f"Carrito/compra por monto inusual detectado: S/ {round(cart_val, 2)} (Usuario: {e.get('user_id')})",
                        "current_value": round(cart_val, 2),
                        "threshold_value": self.config.high_cart_threshold,
                        "window_start": window_start,
                        "window_end": window_end,
                        "detected_at": now_str
                    })
                    break  # Emitir max 1 por ventana

        # 4. Latencia de Procesamiento Alta
        latencies = [e.get("latency_ms", 0) for e in events if "latency_ms" in e]
        if latencies:
            avg_latency = sum(latencies) / float(len(latencies))
            if avg_latency >= self.config.high_latency_threshold_ms:
                alerts.append({
                    "alert_id": f"ALT_LATENCY_{uuid.uuid4().hex[:8]}",
                    "alert_type": "HIGH_LATENCY",
                    "severity": "WARNING",
                    "message": f"Latencia de ingestión elevada: {round(avg_latency, 1)} ms",
                    "current_value": round(avg_latency, 2),
                    "threshold_value": self.config.high_latency_threshold_ms,
                    "window_start": window_start,
                    "window_end": window_end,
                    "detected_at": now_str
                })

        return alerts
