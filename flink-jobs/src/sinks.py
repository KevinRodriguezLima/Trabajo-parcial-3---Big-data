from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional
try:
    import psycopg2
    from psycopg2.extras import Json
    HAS_PSYCOPG2 = True
except ImportError:
    psycopg2 = None
    Json = None
    HAS_PSYCOPG2 = False


from .config import CONFIG

LOGGER = logging.getLogger("flink.sinks")

class PostgresSink:
    """Sink para escribir métricas, audiencias y alertas en PostgreSQL."""
    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn or CONFIG.postgres_dsn
        self._conn = None

    def _get_connection(self):
        if not HAS_PSYCOPG2:
            return None
        if self._conn is None or (hasattr(self._conn, "closed") and self._conn.closed != 0):
            try:
                self._conn = psycopg2.connect(self.dsn)
                self._conn.autocommit = True
            except Exception as e:
                LOGGER.error("Error conectando a Postgres (%s): %s", self.dsn, e)
                return None
        return self._conn


    def write_metric(self, metric_type: str, window_start: str, window_end: str, payload: Dict[str, Any]) -> bool:
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO flink_metrics (metric_type, window_start, window_end, payload, created_at)
                    VALUES (%s, %s, %s, %s, %s);
                    """,
                    (metric_type, window_start, window_end, Json(payload), datetime.now(timezone.utc))
                )
            return True
        except Exception as e:
            LOGGER.error("Error escribiendo metrica en Postgres: %s", e)
            return False

    def write_audience(
        self,
        user_id: str,
        audience_type: str,
        action: str,
        confidence: float,
        evidence: Dict[str, Any],
        detected_at: str,
        expires_at: Optional[str] = None
    ) -> bool:
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audience_classifications
                    (user_id, audience_type, action, confidence, evidence, detected_at, expires_at, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        user_id, audience_type, action, confidence, Json(evidence),
                        detected_at, expires_at, datetime.now(timezone.utc)
                    )
                )
            return True
        except Exception as e:
            LOGGER.error("Error escribiendo audiencia en Postgres: %s", e)
            return False

    def write_alert(
        self,
        alert_id: str,
        alert_type: str,
        severity: str,
        message: str,
        current_value: float,
        threshold_value: float,
        window_start: Optional[str],
        window_end: Optional[str],
        detected_at: str
    ) -> bool:
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO alerts_anomalies
                    (alert_id, alert_type, severity, message, current_value, threshold_value, window_start, window_end, detected_at, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (alert_id) DO UPDATE SET
                        current_value = EXCLUDED.current_value,
                        detected_at = EXCLUDED.detected_at;
                    """,
                    (
                        alert_id, alert_type, severity, message, current_value,
                        threshold_value, window_start, window_end, detected_at,
                        datetime.now(timezone.utc)
                    )
                )
            return True
        except Exception as e:
            LOGGER.error("Error escribiendo alerta en Postgres: %s", e)
            return False

    def close(self):
        if self._conn and self._conn.closed == 0:
            self._conn.close()


class OutputPublisher:
    """
    Publicador unificado que envía los outputs de Flink tanto a Kafka (para D en tiempo real)
    como a Postgres (para persistencia).
    """
    def __init__(self, postgres_sink: Optional[PostgresSink] = None):
        self.pg_sink = postgres_sink or PostgresSink()

    def publish_metric(self, metric_type: str, window_start: str, window_end: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        output_msg = {
            "window_start": window_start,
            "window_end": window_end,
            "metric_type": metric_type,
            "payload": payload,
            "processing_timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.pg_sink.write_metric(metric_type, window_start, window_end, payload)
        return output_msg

    def publish_audience(self, record: Dict[str, Any]) -> Dict[str, Any]:
        self.pg_sink.write_audience(
            user_id=record["user_id"],
            audience_type=record["audience_type"],
            action=record.get("action", "ADDED"),
            confidence=record.get("confidence", 1.0),
            evidence=record.get("evidence", {}),
            detected_at=record["detected_at"],
            expires_at=record.get("expires_at")
        )
        return record

    def publish_alert(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        self.pg_sink.write_alert(
            alert_id=alert["alert_id"],
            alert_type=alert["alert_type"],
            severity=alert["severity"],
            message=alert["message"],
            current_value=alert.get("current_value", 0.0),
            threshold_value=alert.get("threshold_value", 0.0),
            window_start=alert.get("window_start"),
            window_end=alert.get("window_end"),
            detected_at=alert["detected_at"]
        )
        return alert
