import unittest
from src.alerts.anomaly_detector import AnomalyDetector

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

if __name__ == "__main__":
    unittest.main()
