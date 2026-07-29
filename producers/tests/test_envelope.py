from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from producers.envelope import (  # noqa: E402
    build_dead_letter,
    dead_letter_key,
    enrich,
    new_event_id,
    utc_now_iso_ms,
)
from producers.schema import (  # noqa: E402
    PRODUCER_FIELDS,
    SCHEMA_VERSION,
    SOURCE_FIELDS,
    load_required_fields,
)


EVENT_TIMESTAMP = "2026-07-25T18:00:15.928-05:00"


def build_envelope(**overrides: object) -> dict:
    envelope = {
        "source_hint": "MOBILE",
        "event": {
            "event_type": "LOGIN",
            "event_timestamp": EVENT_TIMESTAMP,
            "user_id": "USR000030",
            "session_id": "SES_USR000030_0001",
            "agent_profile": "CLIENTE_ESTACIONAL",
            "city": "Ica",
            "region": "ICA",
            "scenario": "BASE",
            "payload": {"device": "MOBILE_IOS", "is_first_login": True},
        },
    }
    envelope.update(overrides)
    return envelope


class EnrichTests(unittest.TestCase):
    def enriched(self, envelope: dict | None = None) -> dict:
        return enrich(
            envelope if envelope is not None else build_envelope(),
            event_id="evt_0123456789abcdef0123456789abcdef",
            ingestion_timestamp="2026-07-28T22:41:07.512+00:00",
        )

    def test_produces_exactly_the_thirteen_required_fields(self) -> None:
        self.assertEqual(set(self.enriched()), set(load_required_fields()))

    def test_drops_source_hint(self) -> None:
        self.assertNotIn("source_hint", self.enriched())

    def test_copies_the_nine_fields_of_a_verbatim(self) -> None:
        envelope = build_envelope()
        enriched = self.enriched(envelope)
        for field in SOURCE_FIELDS:
            with self.subTest(field=field):
                self.assertEqual(enriched[field], envelope["event"][field])

    def test_never_overwrites_event_timestamp(self) -> None:
        enriched = self.enriched()
        self.assertEqual(enriched["event_timestamp"], EVENT_TIMESTAMP)
        self.assertNotEqual(enriched["ingestion_timestamp"], enriched["event_timestamp"])

    def test_adds_the_four_fields_of_b(self) -> None:
        enriched = self.enriched()
        for field in PRODUCER_FIELDS:
            with self.subTest(field=field):
                self.assertIn(field, enriched)
        self.assertEqual(enriched["schema_version"], SCHEMA_VERSION)

    def test_source_is_the_identity_of_source_hint(self) -> None:
        for source in ("WEB", "MOBILE", "IOT", "VEHICLE", "POS"):
            with self.subTest(source=source):
                enriched = self.enriched(build_envelope(source_hint=source))
                self.assertEqual(enriched["source"], source)

    def test_unknown_source_hint_is_rejected(self) -> None:
        for value in ("SMARTWATCH", "", None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.enriched(build_envelope(source_hint=value))

    def test_missing_source_hint_never_defaults_to_web(self) -> None:
        envelope = build_envelope()
        del envelope["source_hint"]
        with self.assertRaises(ValueError):
            self.enriched(envelope)

    def test_missing_field_of_a_is_reported(self) -> None:
        envelope = build_envelope()
        del envelope["event"]["session_id"]
        with self.assertRaises(ValueError) as ctx:
            self.enriched(envelope)
        self.assertIn("session_id", str(ctx.exception))

    def test_envelope_without_event_is_rejected(self) -> None:
        with self.assertRaises(TypeError):
            self.enriched({"source_hint": "WEB"})


class GeneratedFieldsTests(unittest.TestCase):
    def test_event_id_format(self) -> None:
        self.assertRegex(new_event_id(), r"^evt_[0-9a-f]{32}$")

    def test_event_id_is_unique(self) -> None:
        self.assertEqual(len({new_event_id() for _ in range(1000)}), 1000)

    def test_ingestion_timestamp_is_utc_with_milliseconds(self) -> None:
        value = utc_now_iso_ms()
        self.assertRegex(value, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\+00:00$")
        self.assertEqual(datetime.fromisoformat(value).utcoffset().total_seconds(), 0)


class DeadLetterTests(unittest.TestCase):
    def test_wrapper_shape(self) -> None:
        original = build_envelope()
        wrapper = build_dead_letter(
            original=original,
            error_reason="source_hint fuera del contrato",
            rejected_at="2026-07-28T22:41:07.512+00:00",
        )
        self.assertEqual(list(wrapper), ["error_reason", "rejected_at", "original"])
        self.assertEqual(wrapper["original"], original)

    def test_key_is_user_id_when_available(self) -> None:
        self.assertEqual(dead_letter_key(build_envelope()), "USR000030")

    def test_key_is_none_when_user_id_is_unusable(self) -> None:
        for user_id in ("", None, 42):
            with self.subTest(user_id=user_id):
                envelope = build_envelope()
                envelope["event"]["user_id"] = user_id
                self.assertIsNone(dead_letter_key(envelope))

    def test_key_is_none_for_garbage_input(self) -> None:
        self.assertIsNone(dead_letter_key("{no es json"))
        self.assertIsNone(dead_letter_key({"event": "no es un objeto"}))
        self.assertIsNone(dead_letter_key({}))


if __name__ == "__main__":
    unittest.main()
