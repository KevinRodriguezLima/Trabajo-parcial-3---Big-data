import json
import os
import sys
import unittest
from datetime import datetime, timezone

# Asegurar que el directorio raíz esté ensys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.main import FlinkJobPipeline
from src.sinks import OutputPublisher, PostgresSink

class MockPostgresSink(PostgresSink):
    """Sink mock para capturar las métricas, audiencias y alertas publicadas durante las pruebas de integración."""
    def __init__(self):
        self.published_metrics = []
        self.published_audiences = []
        self.published_alerts = []

    def write_metric(self, metric_type, window_start, window_end, payload):
        self.published_metrics.append({
            "metric_type": metric_type,
            "window_start": window_start,
            "window_end": window_end,
            "payload": payload
        })
        return True

    def write_audience(self, user_id, audience_type, action, confidence, evidence, detected_at, expires_at=None):
        self.published_audiences.append({
            "user_id": user_id,
            "audience_type": audience_type,
            "action": action,
            "confidence": confidence,
            "evidence": evidence,
            "detected_at": detected_at,
            "expires_at": expires_at
        })
        return True

    def write_alert(self, alert_id, alert_type, severity, message, current_value, threshold_value, window_start, window_end, detected_at):
        self.published_alerts.append({
            "alert_id": alert_id,
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "current_value": current_value,
            "threshold_value": threshold_value,
            "window_start": window_start,
            "window_end": window_end,
            "detected_at": detected_at
        })
        return True


class TestPipelineIntegration(unittest.TestCase):
    """
    Prueba de integración End-to-End que simula un flujo real de eventos ingresando al pipeline Flink,
    verificando el cálculo correcto de las 8 métricas, la detección de las 7 audiencias y la emisión de alertas.
    """

    def setUp(self):
        self.pipeline = FlinkJobPipeline()
        self.mock_sink = MockPostgresSink()
        self.pipeline.publisher = OutputPublisher(postgres_sink=self.mock_sink)

    def test_full_pipeline_execution(self):
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Eventos sintéticos diseñados para gatillar métricas, audiencias y alertas
        raw_events = [
            # Evento 1 & 2: Comprador compulsivo (3 compras) y Usuario Alto Valor (> S/ 1000 PEN)
            json.dumps({
                "event_id": "EVT_INT_001",
                "schema_version": "1.0",
                "event_type": "PURCHASE",
                "event_timestamp": now_iso,
                "ingestion_timestamp": now_iso,
                "user_id": "USR_VIP_01",
                "session_id": "SES_01",
                "agent_profile": "COMPRADOR_COMPULSIVO",
                "source": "WEB",
                "city": "Lima",
                "region": "LIMA",
                "scenario": "BLACK_FRIDAY",
                "payload": {
                    "order_id": "ORD_01", "cart_id": "CART_01",
                    "items": [{"product_id": "PROD_LAPTOP", "product_name": "Laptop Gaming", "category": "TECNOLOGIA", "unit_price": 6000.0, "quantity": 1, "subtotal": 6000.0}],
                    "items_count": 1, "total_units": 1, "total_amount": 6000.0, "currency": "PEN", "payment_method": "CREDIT_CARD", "time_to_purchase_ms": 50000
                }

            }),
            json.dumps({
                "event_id": "EVT_INT_002",
                "schema_version": "1.0",
                "event_type": "PURCHASE",
                "event_timestamp": now_iso,
                "ingestion_timestamp": now_iso,
                "user_id": "USR_VIP_01",
                "session_id": "SES_01",
                "agent_profile": "COMPRADOR_COMPULSIVO",
                "source": "WEB",
                "city": "Lima",
                "region": "LIMA",
                "scenario": "BLACK_FRIDAY",
                "payload": {
                    "order_id": "ORD_02", "cart_id": "CART_02",
                    "items": [{"product_id": "PROD_MOUSE", "product_name": "Mouse Gamer", "category": "TECNOLOGIA", "unit_price": 150.0, "quantity": 1, "subtotal": 150.0}],
                    "items_count": 1, "total_units": 1, "total_amount": 150.0, "currency": "PEN", "payment_method": "CREDIT_CARD", "time_to_purchase_ms": 10000
                }
            }),
            json.dumps({
                "event_id": "EVT_INT_003",
                "schema_version": "1.0",
                "event_type": "PURCHASE",
                "event_timestamp": now_iso,
                "ingestion_timestamp": now_iso,
                "user_id": "USR_VIP_01",
                "session_id": "SES_01",
                "agent_profile": "COMPRADOR_COMPULSIVO",
                "source": "MOBILE",
                "city": "Lima",
                "region": "LIMA",
                "scenario": "BLACK_FRIDAY",
                "payload": {
                    "order_id": "ORD_03", "cart_id": "CART_03",
                    "items": [{"product_id": "PROD_KEYBOARD", "product_name": "Teclado Mecanico", "category": "TECNOLOGIA", "unit_price": 300.0, "quantity": 1, "subtotal": 300.0}],
                    "items_count": 1, "total_units": 1, "total_amount": 300.0, "currency": "PEN", "payment_method": "CREDIT_CARD", "time_to_purchase_ms": 12000
                }
            }),
            # Eventos 4 a 8: Fallos masivos de pago (gatillar alerta HIGH_PAYMENT_FAILURE_RATE)
            json.dumps({
                "event_id": "EVT_INT_004", "schema_version": "1.0", "event_type": "PAYMENT_FAILED",
                "event_timestamp": now_iso, "ingestion_timestamp": now_iso, "user_id": "USR_FAIL_01",
                "session_id": "SES_02", "agent_profile": "CLIENTE_INDECISO", "source": "WEB", "city": "Arequipa", "region": "AREQUIPA", "scenario": "BLACK_FRIDAY",
                "payload": {"order_id": "ORD_FAIL_1", "cart_id": "CART_F1", "total_amount": 500.0, "payment_method": "DEBIT_CARD", "failure_reason": "INSUFFICIENT_FUNDS", "retry_count": 1}
            }),
            json.dumps({
                "event_id": "EVT_INT_005", "schema_version": "1.0", "event_type": "PAYMENT_FAILED",
                "event_timestamp": now_iso, "ingestion_timestamp": now_iso, "user_id": "USR_FAIL_02",
                "session_id": "SES_03", "agent_profile": "CLIENTE_INDECISO", "source": "WEB", "city": "Arequipa", "region": "AREQUIPA", "scenario": "BLACK_FRIDAY",
                "payload": {"order_id": "ORD_FAIL_2", "cart_id": "CART_F2", "total_amount": 800.0, "payment_method": "DEBIT_CARD", "failure_reason": "TIMEOUT", "retry_count": 2}
            }),
            json.dumps({
                "event_id": "EVT_INT_006", "schema_version": "1.0", "event_type": "PAYMENT_FAILED",
                "event_timestamp": now_iso, "ingestion_timestamp": now_iso, "user_id": "USR_FAIL_03",
                "session_id": "SES_04", "agent_profile": "CLIENTE_INDECISO", "source": "WEB", "city": "Cusco", "region": "CUSCO", "scenario": "BLACK_FRIDAY",
                "payload": {"order_id": "ORD_FAIL_3", "cart_id": "CART_F3", "total_amount": 1200.0, "payment_method": "CREDIT_CARD", "failure_reason": "CARD_DECLINED", "retry_count": 1}
            }),
            # Evento inválido (para verificar ruta a dead-letter)
            "INVALID_JSON_RAW_STRING_TEST"
        ]

        win_start = "2026-07-25T22:00:00Z"
        win_end = "2026-07-25T22:00:10Z"

        # 2. Ejecutar procesamiento del lote en el pipeline
        self.pipeline.process_batch(raw_events, win_start, win_end)

        # 3. Verificaciones de Métricas Emitidas
        metric_types_emitted = [m["metric_type"] for m in self.mock_sink.published_metrics]
        expected_metrics = [
            "throughput", "active_users", "events_by_type", "top_products_viewed",
            "top_products_purchased", "purchases_by_region", "conversion", "trends"
        ]
        for m_type in expected_metrics:
            self.assertIn(m_type, metric_types_emitted, f"Debe haberse emitido la métrica {m_type}")

        # Verificar Throughput
        tp_metric = next(m for m in self.mock_sink.published_metrics if m["metric_type"] == "throughput")
        self.assertEqual(tp_metric["payload"]["total_events"], 6)

        # Verificar Active Users
        au_metric = next(m for m in self.mock_sink.published_metrics if m["metric_type"] == "active_users")
        self.assertEqual(au_metric["payload"]["active_users_count"], 4)

        # 4. Verificaciones de Clasificación de Audiencias
        audiences_emitted = self.mock_sink.published_audiences
        aud_types_usr_vip = [a["audience_type"] for a in audiences_emitted if a["user_id"] == "USR_VIP_01"]

        self.assertIn("COMPRADOR_COMPULSIVO", aud_types_usr_vip, "USR_VIP_01 debe clasificarse como COMPRADOR_COMPULSIVO")
        self.assertIn("USUARIO_ALTO_VALOR", aud_types_usr_vip, "USR_VIP_01 debe clasificarse como USUARIO_ALTO_VALOR")
        self.assertIn("USUARIO_MULTI_DISPOSITIVO", aud_types_usr_vip, "USR_VIP_01 usó WEB y MOBILE")

        # 5. Verificaciones de Alertas Emitidas
        alerts_emitted = self.mock_sink.published_alerts
        alert_types = [a["alert_type"] for a in alerts_emitted]
        
        self.assertIn("HIGH_PAYMENT_FAILURE_RATE", alert_types, "Debe haberse emitido alerta de alta tasa de fallos de pago")
        self.assertIn("HIGH_VALUE_CART", alert_types, "EVT_INT_001 compra por S/ 4000 excede umbral")

if __name__ == "__main__":
    unittest.main()
