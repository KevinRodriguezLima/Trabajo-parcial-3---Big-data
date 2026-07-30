from datetime import datetime, timezone
import unittest
from src.audiences.classifier import AudienceClassifierRegistry

class TestAudiences(unittest.TestCase):
    def setUp(self):
        self.registry = AudienceClassifierRegistry()

    def test_comprador_compulsivo(self):
        now_iso = datetime.now(timezone.utc).isoformat()
        user_events = [
            {"event_type": "PURCHASE", "event_timestamp": now_iso, "payload": {"total_amount": 100}},
            {"event_type": "PURCHASE", "event_timestamp": now_iso, "payload": {"total_amount": 150}},
            {"event_type": "PURCHASE", "event_timestamp": now_iso, "payload": {"total_amount": 200}}
        ]
        results = self.registry.evaluate_user("USR_COMPULSIVE", user_events)
        aud_types = [r.audience_type for r in results]
        self.assertIn("COMPRADOR_COMPULSIVO", aud_types)

    def test_usuario_alto_valor(self):
        now_iso = datetime.now(timezone.utc).isoformat()
        user_events = [
            {"event_type": "PURCHASE", "event_timestamp": now_iso, "payload": {"total_amount": 1500.0}}
        ]
        results = self.registry.evaluate_user("USR_VIP", user_events)
        aud_types = [r.audience_type for r in results]
        self.assertIn("USUARIO_ALTO_VALOR", aud_types)

    def test_usuario_multi_dispositivo(self):
        now_iso = datetime.now(timezone.utc).isoformat()
        user_events = [
            {"event_type": "PAGE_VIEW", "source": "WEB", "event_timestamp": now_iso},
            {"event_type": "PAGE_VIEW", "source": "MOBILE", "event_timestamp": now_iso}
        ]
        results = self.registry.evaluate_user("USR_MULTI", user_events)
        aud_types = [r.audience_type for r in results]
        self.assertIn("USUARIO_MULTI_DISPOSITIVO", aud_types)

if __name__ == "__main__":
    unittest.main()
