from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from producers.run import Pacer, iter_lines, parse_line  # noqa: E402
from producers.schema import Source  # noqa: E402


ENVELOPE = {
    "source_hint": "MOBILE",
    "event": {
        "event_type": "LOGIN",
        "event_timestamp": "2026-07-25T18:00:15.928-05:00",
        "user_id": "USR000030",
        "session_id": "SES_USR000030_0001",
        "agent_profile": "CLIENTE_ESTACIONAL",
        "city": "Ica",
        "region": "ICA",
        "scenario": "BASE",
        "payload": {"device": "MOBILE_IOS", "is_first_login": True},
    },
}


class ParseLineTests(unittest.TestCase):
    def test_routes_by_source_hint(self) -> None:
        parsed = parse_line(json.dumps(ENVELOPE))
        self.assertTrue(parsed.routable)
        self.assertIs(parsed.source, Source.MOBILE)
        self.assertEqual(parsed.original, ENVELOPE)
        self.assertIsNone(parsed.reason)

    def test_every_source_is_routable(self) -> None:
        for source in Source:
            with self.subTest(source=source.value):
                line = json.dumps(ENVELOPE | {"source_hint": source.value})
                self.assertIs(parse_line(line).source, source)

    def test_broken_json_keeps_the_raw_line(self) -> None:
        parsed = parse_line('{"source_hint": "WEB", "event"\n')
        self.assertFalse(parsed.routable)
        self.assertEqual(parsed.original, '{"source_hint": "WEB", "event"')
        self.assertIn("JSON inválido", parsed.reason or "")

    def test_unknown_source_hint_is_not_routable(self) -> None:
        parsed = parse_line(json.dumps(ENVELOPE | {"source_hint": "SMARTWATCH"}))
        self.assertFalse(parsed.routable)
        self.assertIn("SMARTWATCH", parsed.reason or "")
        self.assertEqual(parsed.original["event"], ENVELOPE["event"])

    def test_missing_source_hint_is_not_routable(self) -> None:
        sin_hint = {"event": ENVELOPE["event"]}
        parsed = parse_line(json.dumps(sin_hint))
        self.assertFalse(parsed.routable)
        self.assertIsNotNone(parsed.reason)

    def test_json_that_is_not_an_object(self) -> None:
        parsed = parse_line("[1, 2, 3]")
        self.assertFalse(parsed.routable)
        self.assertIn("objeto", parsed.reason or "")


class IterLinesTests(unittest.TestCase):
    def write(self, content: str) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "events.jsonl"
        path.write_text(content, encoding="utf-8")
        return path

    def test_skips_blank_lines(self) -> None:
        path = self.write('{"a": 1}\n\n   \n{"b": 2}\n')
        self.assertEqual(len(list(iter_lines(path))), 2)

    def test_limit_counts_lines_read(self) -> None:
        path = self.write("".join(f'{{"n": {index}}}\n' for index in range(10)))
        self.assertEqual(len(list(iter_lines(path, limit=3))), 3)

    def test_limit_zero_reads_nothing(self) -> None:
        path = self.write('{"a": 1}\n')
        self.assertEqual(list(iter_lines(path, limit=0)), [])


class PacerTests(unittest.TestCase):
    def test_without_rate_there_is_no_delay(self) -> None:
        pacer = Pacer(rate=None)
        self.assertEqual(pacer.delay_for(0, now=0.0), 0.0)
        self.assertEqual(pacer.delay_for(1000, now=0.0), 0.0)

    def test_spreads_events_over_the_second(self) -> None:
        pacer = Pacer(rate=10.0)
        self.assertEqual(pacer.delay_for(0, now=100.0), 0.0)
        # El primer envío ancla el reloj: el evento 5 toca en +0,5 s.
        self.assertAlmostEqual(pacer.delay_for(5, now=100.0), 0.5)
        self.assertAlmostEqual(pacer.delay_for(5, now=100.3), 0.2)

    def test_does_not_accumulate_drift(self) -> None:
        pacer = Pacer(rate=100.0)
        pacer.delay_for(0, now=0.0)
        # Si una línea tardó de más, el objetivo sigue siendo absoluto.
        self.assertEqual(pacer.delay_for(10, now=5.0), 0.0)

    def test_never_returns_negative_delay(self) -> None:
        pacer = Pacer(rate=1.0)
        pacer.delay_for(0, now=0.0)
        self.assertEqual(pacer.delay_for(1, now=999.0), 0.0)

    def test_rate_zero_is_treated_as_unlimited(self) -> None:
        self.assertEqual(Pacer(rate=0.0).delay_for(10, now=0.0), 0.0)


if __name__ == "__main__":
    unittest.main()
