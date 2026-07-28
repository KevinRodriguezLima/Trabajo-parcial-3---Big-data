from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from producers.schema import load_required_fields  # noqa: E402
from producers.store import (  # noqa: E402
    EVENT_COLUMNS,
    INSERT_EVENTS,
    Batch,
    dsn_from_env,
    row_from_event,
)


EVENT = {
    "event_id": "evt_0123456789abcdef0123456789abcdef",
    "schema_version": "1.0",
    "event_type": "LOGIN",
    "event_timestamp": "2026-07-25T18:00:15.928-05:00",
    "ingestion_timestamp": "2026-07-28T22:41:07.512+00:00",
    "user_id": "USR000030",
    "session_id": "SES_USR000030_0001",
    "agent_profile": "CLIENTE_FRECUENTE",
    "source": "MOBILE",
    "city": "Ica",
    "region": "ICA",
    "scenario": "BASE",
    "payload": {"device": "MOBILE_IOS", "is_first_login": True},
}


class ColumnTests(unittest.TestCase):
    def test_columns_cover_the_thirteen_contract_fields(self) -> None:
        self.assertEqual(set(load_required_fields()) - set(EVENT_COLUMNS), set())

    def test_kafka_coordinates_are_prefixed(self) -> None:
        # `offset` y `partition` son palabras reservadas en SQL.
        self.assertIn("kafka_topic", EVENT_COLUMNS)
        self.assertIn("kafka_partition", EVENT_COLUMNS)
        self.assertIn("kafka_offset", EVENT_COLUMNS)
        self.assertNotIn("offset", EVENT_COLUMNS)

    def test_insert_deduplicates_by_event_id(self) -> None:
        self.assertIn("ON CONFLICT (event_id) DO NOTHING", INSERT_EVENTS)

    def test_insert_has_one_placeholder_per_column(self) -> None:
        self.assertEqual(INSERT_EVENTS.count("%s"), len(EVENT_COLUMNS))

    def test_payload_is_cast_to_jsonb(self) -> None:
        self.assertIn("%s::jsonb", INSERT_EVENTS)


class RowTests(unittest.TestCase):
    def row(self) -> tuple:
        return row_from_event(EVENT, topic="user-events", partition=2, offset=41)

    def test_row_matches_column_order(self) -> None:
        row = self.row()
        self.assertEqual(len(row), len(EVENT_COLUMNS))
        valores = dict(zip(EVENT_COLUMNS, row))
        self.assertEqual(valores["event_id"], EVENT["event_id"])
        self.assertEqual(valores["source"], "MOBILE")
        self.assertEqual(valores["kafka_topic"], "user-events")
        self.assertEqual(valores["kafka_partition"], 2)
        self.assertEqual(valores["kafka_offset"], 41)

    def test_payload_travels_as_json_text(self) -> None:
        valores = dict(zip(EVENT_COLUMNS, self.row()))
        self.assertIsInstance(valores["payload"], str)
        self.assertEqual(json.loads(valores["payload"]), EVENT["payload"])

    def test_event_timestamp_is_not_rewritten(self) -> None:
        valores = dict(zip(EVENT_COLUMNS, self.row()))
        self.assertEqual(valores["event_timestamp"], EVENT["event_timestamp"])
        self.assertNotEqual(valores["event_timestamp"], valores["ingestion_timestamp"])

    def test_incomplete_event_is_rejected(self) -> None:
        incompleto = {key: value for key, value in EVENT.items() if key != "city"}
        with self.assertRaises(KeyError):
            row_from_event(incompleto, topic="user-events", partition=0, offset=0)


class BatchTests(unittest.TestCase):
    def test_empty_batch_never_flushes(self) -> None:
        self.assertFalse(Batch().should_flush(now=1000.0))

    def test_flushes_when_full(self) -> None:
        batch = Batch(max_rows=3, max_seconds=60.0)
        for index in range(2):
            batch.add((index,), now=0.0)
        self.assertFalse(batch.should_flush(now=0.5))
        batch.add((2,), now=0.5)
        self.assertTrue(batch.should_flush(now=0.5))

    def test_flushes_when_the_window_expires(self) -> None:
        batch = Batch(max_rows=500, max_seconds=2.0)
        batch.add((1,), now=100.0)
        self.assertFalse(batch.should_flush(now=101.9))
        self.assertTrue(batch.should_flush(now=102.0))

    def test_window_starts_with_the_first_row(self) -> None:
        batch = Batch(max_rows=500, max_seconds=2.0)
        batch.add((1,), now=100.0)
        batch.add((2,), now=101.5)
        self.assertTrue(batch.should_flush(now=102.0))

    def test_drain_empties_and_resets_the_window(self) -> None:
        batch = Batch(max_rows=2, max_seconds=2.0)
        batch.add((1,), now=100.0)
        batch.add((2,), now=100.1)
        self.assertEqual(batch.drain(), [(1,), (2,)])
        self.assertEqual(len(batch), 0)
        self.assertIsNone(batch.opened_at)
        self.assertFalse(batch.should_flush(now=200.0))

    def test_window_restarts_after_drain(self) -> None:
        batch = Batch(max_rows=500, max_seconds=2.0)
        batch.add((1,), now=100.0)
        batch.drain()
        batch.add((2,), now=101.0)
        self.assertFalse(batch.should_flush(now=102.0))
        self.assertTrue(batch.should_flush(now=103.0))


class DsnTests(unittest.TestCase):
    def test_environment_wins(self) -> None:
        self.assertEqual(
            dsn_from_env({"POSTGRES_DSN": "postgresql://x/y"}), "postgresql://x/y"
        )

    def test_falls_back_to_the_local_default(self) -> None:
        self.assertIn("localhost:5432", dsn_from_env({}))


if __name__ == "__main__":
    unittest.main()
