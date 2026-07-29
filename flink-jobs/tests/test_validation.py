import json
import unittest
from src.validation import EventValidator
from src.schemas import validate_raw_event

class TestValidation(unittest.TestCase):
    def setUp(self):
        self.valid_event_dict = {
            "event_id": "evt_test_001",
            "schema_version": "1.0",
            "event_type": "VIEW_PRODUCT",
            "event_timestamp": "2026-07-25T22:14:03.482Z",
            "ingestion_timestamp": "2026-07-25T22:14:03.610Z",
            "user_id": "USR0001",
            "session_id": "SES0001",
            "agent_profile": "COMPARADOR",
            "source": "WEB",
            "city": "Arequipa",
            "region": "AREQUIPA",
            "scenario": "CYBER_MONDAY",
            "payload": {
                "product_id": "P001",
                "product_name": "Test Laptop",
                "category": "TECNOLOGIA",
                "price": 2000.0,
                "dwell_time_ms": 5000
            }
        }

    def test_valid_event_schema(self):
        raw = json.dumps(self.valid_event_dict)
        is_valid, parsed, error = validate_raw_event(raw)
        self.assertTrue(is_valid)
        self.assertIsNone(error)
        self.assertEqual(parsed["event_id"], "evt_test_001")

    def test_missing_required_field(self):
        invalid_dict = dict(self.valid_event_dict)
        del invalid_dict["user_id"]
        raw = json.dumps(invalid_dict)
        is_valid, parsed, error = validate_raw_event(raw)
        self.assertFalse(is_valid)
        self.assertIn("user_id", error)

    def test_invalid_event_type(self):
        invalid_dict = dict(self.valid_event_dict)
        invalid_dict["event_type"] = "NON_EXISTENT_TYPE"
        raw = json.dumps(invalid_dict)
        is_valid, parsed, error = validate_raw_event(raw)
        self.assertFalse(is_valid)
        self.assertIn("event_type", error)

    def test_validator_deduplication(self):
        validator = EventValidator()
        raw = json.dumps(self.valid_event_dict)

        # Primer procesado ok
        is_valid, enriched, dl = validator.process(raw)
        self.assertTrue(is_valid)
        self.assertIsNotNone(enriched)

        # Segundo procesado con mismo event_id => duplicado en dead_letter
        is_valid2, enriched2, dl2 = validator.process(raw)
        self.assertFalse(is_valid2)
        self.assertIsNotNone(dl2)
        self.assertIn("Duplicate", dl2["error_reason"])

if __name__ == "__main__":
    unittest.main()
