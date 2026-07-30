from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import yaml


CONTRACTS_DIR = Path(__file__).resolve().parents[1] / "contracts"
TOPICS_PATH = CONTRACTS_DIR / "topics.yaml"
EVENT_SCHEMA_PATH = CONTRACTS_DIR / "event.schema.json"

SCHEMA_VERSION = "1.0"
DEAD_LETTER_TOPIC = "dead-letter"
PARTITION_KEY_FIELD = "user_id"

# Los nueve campos que entrega A y se copian verbatim.
SOURCE_FIELDS: tuple[str, ...] = (
    "event_type",
    "event_timestamp",
    "user_id",
    "session_id",
    "agent_profile",
    "city",
    "region",
    "scenario",
    "payload",
)

# Los cuatro campos que agrega B.
PRODUCER_FIELDS: tuple[str, ...] = (
    "event_id",
    "schema_version",
    "ingestion_timestamp",
    "source",
)


class EventType(str, Enum):
    LOGIN = "LOGIN"
    SEARCH = "SEARCH"
    PAGE_VIEW = "PAGE_VIEW"
    VIEW_PRODUCT = "VIEW_PRODUCT"
    ADD_TO_CART = "ADD_TO_CART"
    REMOVE_FROM_CART = "REMOVE_FROM_CART"
    PURCHASE = "PURCHASE"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    GPS_UPDATE = "GPS_UPDATE"
    IOT_READING = "IOT_READING"
    MOTION_DETECTED = "MOTION_DETECTED"
    SOCIAL_POST = "SOCIAL_POST"


class Source(str, Enum):
    WEB = "WEB"
    MOBILE = "MOBILE"
    IOT = "IOT"
    VEHICLE = "VEHICLE"
    POS = "POS"


@dataclass(frozen=True, slots=True)
class TopicSpec:
    name: str
    partitions: int
    event_types: tuple[EventType, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "partitions": self.partitions,
            "event_types": [event_type.value for event_type in self.event_types],
        }


@dataclass(frozen=True, slots=True)
class TopicConflict:
    name: str
    expected_partitions: int
    actual_partitions: int

    def describe(self) -> str:
        return (
            f"{self.name}: el contrato exige {self.expected_partitions} particiones "
            f"y el broker tiene {self.actual_partitions}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "expected_partitions": self.expected_partitions,
            "actual_partitions": self.actual_partitions,
        }


@dataclass(frozen=True, slots=True)
class TopicPlan:
    to_create: tuple[TopicSpec, ...]
    unchanged: tuple[TopicSpec, ...]
    conflicts: tuple[TopicConflict, ...]

    @property
    def has_conflicts(self) -> bool:
        return bool(self.conflicts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "to_create": [spec.to_dict() for spec in self.to_create],
            "unchanged": [spec.to_dict() for spec in self.unchanged],
            "conflicts": [conflict.to_dict() for conflict in self.conflicts],
        }


def _as_event_type(topic: str, value: str) -> EventType:
    try:
        return EventType(value)
    except ValueError as exc:
        raise ValueError(f"{topic} declara un event_type fuera del contrato: {value!r}") from exc


def load_topic_specs(path: Path = TOPICS_PATH) -> tuple[TopicSpec, ...]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    partition_key = raw.get("partition_key")
    if partition_key != PARTITION_KEY_FIELD:
        raise ValueError(
            f"El contrato exige particionar por {PARTITION_KEY_FIELD!r}, no por {partition_key!r}"
        )
    topics = raw.get("topics")
    if not isinstance(topics, dict) or not topics:
        raise ValueError("topics.yaml no declara ningún topic")

    specs: list[TopicSpec] = []
    for name, body in topics.items():
        partitions = int(body["partitions"])
        if partitions < 1:
            raise ValueError(f"{name} declara {partitions} particiones")
        event_types = tuple(
            _as_event_type(name, value) for value in body.get("event_types") or ()
        )
        specs.append(TopicSpec(name=name, partitions=partitions, event_types=event_types))
    return tuple(specs)


def load_output_topic_specs(path: Path = TOPICS_PATH) -> tuple[TopicSpec, ...]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    output_topics = raw.get("output_topics") or {}
    if not isinstance(output_topics, dict):
        raise ValueError("topics.yaml declara output_topics con una forma invalida")

    specs: list[TopicSpec] = []
    for name, body in output_topics.items():
        partitions = int(body["partitions"])
        if partitions < 1:
            raise ValueError(f"{name} declara {partitions} particiones")
        specs.append(TopicSpec(name=name, partitions=partitions, event_types=()))
    return tuple(specs)


def build_topic_by_event(specs: Iterable[TopicSpec]) -> dict[EventType, str]:
    mapping: dict[EventType, str] = {}
    for spec in specs:
        for event_type in spec.event_types:
            previous = mapping.get(event_type)
            if previous is not None:
                raise ValueError(
                    f"{event_type.value} está enrutado a {previous} y también a {spec.name}"
                )
            mapping[event_type] = spec.name

    missing = sorted(set(EventType) - set(mapping))
    if missing:
        raise ValueError(
            f"Sin topic asignado: {[event_type.value for event_type in missing]}"
        )
    return mapping


def partitions_by_topic(specs: Iterable[TopicSpec]) -> dict[str, int]:
    return {spec.name: spec.partitions for spec in specs}


def plan_topics(specs: Iterable[TopicSpec], existing: Mapping[str, int]) -> TopicPlan:
    to_create: list[TopicSpec] = []
    unchanged: list[TopicSpec] = []
    conflicts: list[TopicConflict] = []

    for spec in specs:
        actual = existing.get(spec.name)
        if actual is None:
            to_create.append(spec)
        elif actual == spec.partitions:
            unchanged.append(spec)
        else:
            conflicts.append(
                TopicConflict(
                    name=spec.name,
                    expected_partitions=spec.partitions,
                    actual_partitions=actual,
                )
            )
    return TopicPlan(
        to_create=tuple(to_create),
        unchanged=tuple(unchanged),
        conflicts=tuple(conflicts),
    )


def topic_for_event(event_type: EventType | str) -> str:
    try:
        return TOPIC_BY_EVENT[EventType(event_type)]
    except (KeyError, ValueError) as exc:
        raise ValueError(f"event_type sin ruta en el contrato: {event_type!r}") from exc


def load_schema_enum(field: str, path: Path = EVENT_SCHEMA_PATH) -> tuple[str, ...]:
    schema = json.loads(path.read_text(encoding="utf-8"))
    return tuple(schema["properties"][field]["enum"])


def load_required_fields(path: Path = EVENT_SCHEMA_PATH) -> tuple[str, ...]:
    schema = json.loads(path.read_text(encoding="utf-8"))
    return tuple(schema["required"])


TOPIC_SPECS: tuple[TopicSpec, ...] = load_topic_specs()
OUTPUT_TOPIC_SPECS: tuple[TopicSpec, ...] = load_output_topic_specs()
ALL_TOPIC_SPECS: tuple[TopicSpec, ...] = TOPIC_SPECS + OUTPUT_TOPIC_SPECS
TOPIC_BY_EVENT: dict[EventType, str] = build_topic_by_event(TOPIC_SPECS)
BUSINESS_TOPICS: tuple[str, ...] = tuple(
    spec.name for spec in TOPIC_SPECS if spec.name != DEAD_LETTER_TOPIC
)
