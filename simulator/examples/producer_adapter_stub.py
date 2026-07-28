from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from simulator.enums import EventType
from simulator.models import GeneratedMessage


TOPIC_BY_EVENT: dict[EventType, str] = {
    EventType.LOGIN: "user-events",
    EventType.SEARCH: "user-events",
    EventType.PAGE_VIEW: "user-events",
    EventType.VIEW_PRODUCT: "user-events",
    EventType.ADD_TO_CART: "user-events",
    EventType.REMOVE_FROM_CART: "user-events",
    EventType.PURCHASE: "purchase-events",
    EventType.PAYMENT_FAILED: "purchase-events",
    EventType.GPS_UPDATE: "iot-events",
    EventType.IOT_READING: "iot-events",
    EventType.MOTION_DETECTED: "iot-events",
    EventType.SOCIAL_POST: "system-events",
}


def enrich_for_producer(message: GeneratedMessage) -> tuple[str, str, dict]:
    raw = message.event.to_dict()
    envelope = {
        "event_id": f"evt_{uuid4().hex}",
        "schema_version": "1.0",
        **raw,
        "ingestion_timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "source": message.source_hint.value,
    }
    topic = TOPIC_BY_EVENT[message.event.event_type]
    partition_key = message.event.user_id
    return topic, partition_key, envelope
