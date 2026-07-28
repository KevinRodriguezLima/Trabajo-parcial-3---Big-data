from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from producers.envelope import enrich  # noqa: E402
from producers.schema import SOURCE_FIELDS, EventType  # noqa: E402
from producers.validation import (  # noqa: E402
    ENVELOPE_RULES,
    ITEM_REQUIREMENTS,
    PAYLOAD_REQUIREMENTS,
    ValidationError,
    validate_event,
    validate_input,
)


PAYLOADS: dict[EventType, dict] = {
    EventType.LOGIN: {"device": "WEB_DESKTOP", "is_first_login": True},
    EventType.SEARCH: {"query": "laptop", "results_count": 12, "category_filter": "TECNOLOGIA"},
    EventType.PAGE_VIEW: {"page_type": "HOME", "page_url": "/", "dwell_time_ms": 1200},
    EventType.VIEW_PRODUCT: {
        "product_id": "P042",
        "product_name": "Laptop",
        "category": "TECNOLOGIA",
        "price": 3499.9,
        "dwell_time_ms": 8700,
    },
    EventType.ADD_TO_CART: {
        "cart_id": "CART_1",
        "product_id": "P042",
        "product_name": "Laptop",
        "category": "TECNOLOGIA",
        "unit_price": 3499.9,
        "quantity": 1,
        "cart_size_after": 1,
        "cart_value_after": 3499.9,
    },
    EventType.REMOVE_FROM_CART: {
        "cart_id": "CART_1",
        "product_id": "P042",
        "quantity": 1,
        "cart_size_after": 0,
        "cart_value_after": 0,
    },
    EventType.PURCHASE: {
        "order_id": "ORD_1",
        "cart_id": "CART_1",
        "items": [
            {
                "product_id": "P042",
                "product_name": "Laptop",
                "category": "TECNOLOGIA",
                "unit_price": 3499.9,
                "quantity": 1,
                "subtotal": 3499.9,
            }
        ],
        "items_count": 1,
        "total_units": 1,
        "total_amount": 3499.9,
        "currency": "PEN",
        "payment_method": "YAPE",
        "time_to_purchase_ms": 142000,
    },
    EventType.PAYMENT_FAILED: {
        "order_id": "ORD_1",
        "cart_id": "CART_1",
        "total_amount": 3499.9,
        "payment_method": "YAPE",
        "failure_reason": "TIMEOUT",
        "retry_count": 3,
    },
    EventType.GPS_UPDATE: {
        "device_id": "DEV_1",
        "latitude": -16.4,
        "longitude": -71.5,
        "speed_kmh": 24.1,
    },
    EventType.IOT_READING: {
        "device_id": "SEN_1",
        "sensor_type": "HUMIDITY",
        "value": 32.5,
        "unit": "PERCENT",
    },
    EventType.MOTION_DETECTED: {"device_id": "SEN_1", "zone": "CAJA", "confidence": 0.86},
    EventType.SOCIAL_POST: {
        "platform": "FACEBOOK",
        "post_type": "COMMENT",
        "product_id": "P006",
        "sentiment": "POSITIVE",
    },
}


def envelope_for(event_type: EventType, **overrides) -> dict:
    envelope = {
        "source_hint": "WEB",
        "event": {
            "event_type": event_type.value,
            "event_timestamp": "2026-07-25T18:00:15.928-05:00",
            "user_id": "USR000030",
            "session_id": "SES_USR000030_0001",
            "agent_profile": "CLIENTE_FRECUENTE",
            "city": "Arequipa",
            "region": "AREQUIPA",
            "scenario": "BASE",
            "payload": deepcopy(PAYLOADS[event_type]),
        },
    }
    envelope.update(overrides)
    return envelope


class ContractTableTests(unittest.TestCase):
    def test_payload_requirements_cover_the_twelve_types(self) -> None:
        self.assertEqual(set(PAYLOAD_REQUIREMENTS), set(EventType))

    def test_requirements_come_from_the_contract(self) -> None:
        self.assertEqual(
            PAYLOAD_REQUIREMENTS[EventType.LOGIN], frozenset({"device", "is_first_login"})
        )
        self.assertIn("items", PAYLOAD_REQUIREMENTS[EventType.PURCHASE])
        self.assertIn("subtotal", ITEM_REQUIREMENTS)

    def test_envelope_rules_come_from_the_contract(self) -> None:
        self.assertEqual(len(ENVELOPE_RULES.required), 13)
        self.assertEqual(ENVELOPE_RULES.consts["schema_version"], "1.0")
        self.assertIn("event_type", ENVELOPE_RULES.enums)
        self.assertIn("source", ENVELOPE_RULES.enums)
        self.assertEqual(
            ENVELOPE_RULES.timestamps, frozenset({"event_timestamp", "ingestion_timestamp"})
        )


class ValidateInputTests(unittest.TestCase):
    def test_every_event_type_passes_with_its_payload(self) -> None:
        for event_type in EventType:
            with self.subTest(event_type=event_type.value):
                validate_input(envelope_for(event_type))

    def test_missing_event_type_is_detected_first(self) -> None:
        envelope = envelope_for(EventType.LOGIN)
        del envelope["event"]["event_type"]
        del envelope["event"]["user_id"]
        with self.assertRaises(ValidationError) as ctx:
            validate_input(envelope)
        # El motivo debe hablar de event_type, no de los doce payloads a la vez.
        self.assertEqual(str(ctx.exception), "Falta event_type")

    def test_unknown_event_type(self) -> None:
        envelope = envelope_for(EventType.LOGIN)
        envelope["event"]["event_type"] = "SCENARIO_CHANGE"
        with self.assertRaises(ValidationError) as ctx:
            validate_input(envelope)
        self.assertIn("SCENARIO_CHANGE", str(ctx.exception))

    def test_each_missing_field_of_a_is_reported(self) -> None:
        for field in SOURCE_FIELDS:
            if field == "event_type":
                continue
            with self.subTest(field=field):
                envelope = envelope_for(EventType.LOGIN)
                del envelope["event"][field]
                with self.assertRaises(ValidationError) as ctx:
                    validate_input(envelope)
                self.assertIn(field, str(ctx.exception))

    def test_empty_strings_are_rejected(self) -> None:
        for field in ("user_id", "session_id", "city", "region", "event_timestamp"):
            with self.subTest(field=field):
                envelope = envelope_for(EventType.LOGIN)
                envelope["event"][field] = ""
                with self.assertRaises(ValidationError):
                    validate_input(envelope)

    def test_incomplete_payload_per_event_type(self) -> None:
        for event_type in EventType:
            required = sorted(PAYLOAD_REQUIREMENTS[event_type])
            with self.subTest(event_type=event_type.value):
                envelope = envelope_for(event_type)
                del envelope["event"]["payload"][required[0]]
                with self.assertRaises(ValidationError) as ctx:
                    validate_input(envelope)
                self.assertIn(required[0], str(ctx.exception))

    def test_purchase_needs_non_empty_items(self) -> None:
        envelope = envelope_for(EventType.PURCHASE)
        envelope["event"]["payload"]["items"] = []
        with self.assertRaises(ValidationError):
            validate_input(envelope)

    def test_purchase_item_must_be_complete(self) -> None:
        envelope = envelope_for(EventType.PURCHASE)
        del envelope["event"]["payload"]["items"][0]["subtotal"]
        with self.assertRaises(ValidationError) as ctx:
            validate_input(envelope)
        self.assertIn("subtotal", str(ctx.exception))

    def test_source_hint_is_validated(self) -> None:
        for value in ("SMARTWATCH", "", None):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    validate_input(envelope_for(EventType.LOGIN, source_hint=value))

    def test_garbage_input(self) -> None:
        for value in ("no soy json", [], None, {"event": "texto"}):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    validate_input(value)

    def test_payload_must_be_object(self) -> None:
        envelope = envelope_for(EventType.LOGIN)
        envelope["event"]["payload"] = "texto"
        with self.assertRaises(ValidationError):
            validate_input(envelope)


class ValidateEventTests(unittest.TestCase):
    def enriched(self, event_type: EventType = EventType.LOGIN) -> dict:
        return enrich(
            envelope_for(event_type),
            event_id="evt_0123456789abcdef0123456789abcdef",
            ingestion_timestamp="2026-07-28T22:41:07.512+00:00",
        )

    def test_enriched_event_passes(self) -> None:
        for event_type in EventType:
            with self.subTest(event_type=event_type.value):
                validate_event(self.enriched(event_type))

    def test_extra_field_is_rejected(self) -> None:
        event = self.enriched()
        event["source_hint"] = "WEB"
        with self.assertRaises(ValidationError) as ctx:
            validate_event(event)
        self.assertIn("source_hint", str(ctx.exception))

    def test_missing_field_is_rejected(self) -> None:
        event = self.enriched()
        del event["event_id"]
        with self.assertRaises(ValidationError) as ctx:
            validate_event(event)
        self.assertIn("event_id", str(ctx.exception))

    def test_wrong_schema_version(self) -> None:
        event = self.enriched()
        event["schema_version"] = "2.0"
        with self.assertRaises(ValidationError):
            validate_event(event)

    def test_enum_values_are_checked(self) -> None:
        for field, value in (
            ("source", "SMARTWATCH"),
            ("scenario", "HALLOWEEN"),
            ("agent_profile", "CLIENTE_NUEVO"),
            ("event_type", "SCENARIO_CHANGE"),
        ):
            with self.subTest(field=field):
                event = self.enriched()
                event[field] = value
                with self.assertRaises(ValidationError):
                    validate_event(event)

    def test_timestamps_must_carry_timezone(self) -> None:
        for field in ("event_timestamp", "ingestion_timestamp"):
            with self.subTest(field=field):
                event = self.enriched()
                event[field] = "2026-07-25T18:00:15.928"
                with self.assertRaises(ValidationError) as ctx:
                    validate_event(event)
                self.assertIn("zona horaria", str(ctx.exception))

    def test_timestamps_must_be_iso(self) -> None:
        event = self.enriched()
        event["event_timestamp"] = "25/07/2026 18:00"
        with self.assertRaises(ValidationError):
            validate_event(event)

    def test_empty_identifier_is_rejected(self) -> None:
        event = self.enriched()
        event["user_id"] = ""
        with self.assertRaises(ValidationError):
            validate_event(event)


if __name__ == "__main__":
    unittest.main()
