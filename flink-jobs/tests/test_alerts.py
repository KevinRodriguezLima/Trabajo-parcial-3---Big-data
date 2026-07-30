import unittest
from src.alerts.anomaly_detector import AnomalyDetector
from src.config import AnomalyConfig

class TestAlerts(unittest.TestCase):
    def setUp(self):
        self.detector = AnomalyDetector()

    def test_high_payment_failure_alert(self):
        events = [
            {"event_type": "PURCHASE", "payload": {}},
            {"event_type": "PAYMENT_FAILED", "payload": {}},
            {"event_type": "PAYMENT_FAILED", "payload": {}},
            {"event_type": "PAYMENT_FAILED", "payload": {}},
            {"event_type": "PAYMENT_FAILED", "payload": {}}
        ]
        alerts = self.detector.detect(events, "2026-07-25T22:00:00Z", "2026-07-25T22:00:10Z")
        alert_types = [a["alert_type"] for a in alerts]
        self.assertIn("HIGH_PAYMENT_FAILURE_RATE", alert_types)

    def test_high_value_cart_alert(self):
        events = [
            {"event_type": "ADD_TO_CART", "user_id": "USR99", "payload": {"cart_value_after": 6000.0}}
        ]
        alerts = self.detector.detect(events, "2026-07-25T22:00:00Z", "2026-07-25T22:00:10Z")
        alert_types = [a["alert_type"] for a in alerts]
        self.assertIn("HIGH_VALUE_CART", alert_types)

    def test_high_value_payment_failure_alert(self):
        detector = AnomalyDetector(AnomalyConfig(critical_payment_amount_pen=1000.0))
        events = [
            {"event_type": "PAYMENT_FAILED", "payload": {"total_amount": 1450.0}},
        ]
        alerts = detector.detect(events, "2026-07-25T22:00:00Z", "2026-07-25T22:00:10Z")
        alert_types = [a["alert_type"] for a in alerts]
        self.assertIn("HIGH_VALUE_PAYMENT_FAILURE", alert_types)

    def test_high_cart_activity_warning(self):
        detector = AnomalyDetector(AnomalyConfig(cart_activity_min=3))
        events = [
            {"event_type": "ADD_TO_CART", "payload": {"cart_value_after": 100.0}},
            {"event_type": "REMOVE_FROM_CART", "payload": {"cart_value_after": 0.0}},
            {"event_type": "ADD_TO_CART", "payload": {"cart_value_after": 120.0}},
        ]
        alerts = detector.detect(events, "2026-07-25T22:00:00Z", "2026-07-25T22:00:10Z")
        alert_types = [a["alert_type"] for a in alerts]
        self.assertIn("HIGH_CART_ACTIVITY", alert_types)

if __name__ == "__main__":
    unittest.main()
