from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from producers.schema import (  # noqa: E402
    BUSINESS_TOPICS,
    DEAD_LETTER_TOPIC,
    TOPIC_BY_EVENT,
    TOPIC_SPECS,
    EventType,
    Source,
    TopicSpec,
    build_topic_by_event,
    load_required_fields,
    load_schema_enum,
    load_topic_specs,
    partitions_by_topic,
    plan_topics,
    topic_for_event,
)


class ContractTests(unittest.TestCase):
    def test_event_type_enum_matches_contract(self) -> None:
        self.assertEqual(
            sorted(load_schema_enum("event_type")),
            sorted(event_type.value for event_type in EventType),
        )

    def test_source_enum_matches_contract(self) -> None:
        self.assertEqual(
            sorted(load_schema_enum("source")),
            sorted(source.value for source in Source),
        )

    def test_required_fields_are_thirteen(self) -> None:
        required = load_required_fields()
        self.assertEqual(len(required), 13)
        self.assertNotIn("source_hint", required)

    def test_every_event_type_has_topic(self) -> None:
        self.assertEqual(set(TOPIC_BY_EVENT), set(EventType))

    def test_partitions_match_contract(self) -> None:
        self.assertEqual(
            partitions_by_topic(TOPIC_SPECS),
            {
                "user-events": 4,
                "purchase-events": 2,
                "iot-events": 2,
                "system-events": 1,
                "dead-letter": 1,
            },
        )

    def test_dead_letter_has_no_event_types(self) -> None:
        dead_letter = next(spec for spec in TOPIC_SPECS if spec.name == DEAD_LETTER_TOPIC)
        self.assertEqual(dead_letter.event_types, ())
        self.assertNotIn(DEAD_LETTER_TOPIC, BUSINESS_TOPICS)

    def test_routing_is_by_event_type_not_by_source(self) -> None:
        self.assertEqual(topic_for_event(EventType.LOGIN), "user-events")
        self.assertEqual(topic_for_event("PURCHASE"), "purchase-events")
        self.assertEqual(topic_for_event(EventType.GPS_UPDATE), "iot-events")
        self.assertEqual(topic_for_event(EventType.SOCIAL_POST), "system-events")

    def test_unknown_event_type_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            topic_for_event("SCENARIO_CHANGE")

    def test_duplicated_routing_is_rejected(self) -> None:
        specs = (
            TopicSpec(name="a", partitions=1, event_types=(EventType.LOGIN,)),
            TopicSpec(name="b", partitions=1, event_types=(EventType.LOGIN,)),
        )
        with self.assertRaises(ValueError):
            build_topic_by_event(specs)

    def test_uncovered_event_type_is_rejected(self) -> None:
        specs = (TopicSpec(name="a", partitions=1, event_types=(EventType.LOGIN,)),)
        with self.assertRaises(ValueError):
            build_topic_by_event(specs)

    def test_unknown_event_type_in_yaml_is_rejected(self) -> None:
        path = self._write_yaml(
            'version: "1.0"\n'
            "partition_key: user_id\n"
            "topics:\n"
            "  user-events:\n"
            "    partitions: 4\n"
            "    event_types: [SCENARIO_CHANGE]\n"
        )
        with self.assertRaises(ValueError):
            load_topic_specs(path)

    def test_wrong_partition_key_is_rejected(self) -> None:
        path = self._write_yaml(
            'version: "1.0"\n'
            "partition_key: session_id\n"
            "topics:\n"
            "  user-events:\n"
            "    partitions: 4\n"
            "    event_types: [LOGIN]\n"
        )
        with self.assertRaises(ValueError):
            load_topic_specs(path)

    def _write_yaml(self, content: str) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "topics.yaml"
        path.write_text(content, encoding="utf-8")
        return path


class TopicPlanTests(unittest.TestCase):
    def test_creates_what_is_missing(self) -> None:
        plan = plan_topics(TOPIC_SPECS, {})
        self.assertEqual(len(plan.to_create), len(TOPIC_SPECS))
        self.assertEqual(plan.unchanged, ())
        self.assertFalse(plan.has_conflicts)

    def test_is_idempotent_when_everything_matches(self) -> None:
        plan = plan_topics(TOPIC_SPECS, partitions_by_topic(TOPIC_SPECS))
        self.assertEqual(plan.to_create, ())
        self.assertEqual(len(plan.unchanged), len(TOPIC_SPECS))
        self.assertFalse(plan.has_conflicts)

    def test_detects_partition_drift(self) -> None:
        existing = partitions_by_topic(TOPIC_SPECS) | {"user-events": 1}
        plan = plan_topics(TOPIC_SPECS, existing)
        self.assertTrue(plan.has_conflicts)
        self.assertEqual(plan.conflicts[0].name, "user-events")
        self.assertEqual(plan.conflicts[0].expected_partitions, 4)
        self.assertEqual(plan.conflicts[0].actual_partitions, 1)
        self.assertNotIn("user-events", [spec.name for spec in plan.to_create])


if __name__ == "__main__":
    unittest.main()
