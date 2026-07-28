from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .enums import AgentProfile, EventType, Scenario, SourceHint


@dataclass(frozen=True, slots=True)
class Product:
    product_id: str
    product_name: str
    category: str
    base_price: float
    popularity: float = 1.0


@dataclass(frozen=True, slots=True)
class Location:
    city: str
    region: str
    latitude: float
    longitude: float
    weight: float = 1.0


@dataclass(slots=True)
class CartItem:
    product: Product
    unit_price: float
    quantity: int = 1

    @property
    def subtotal(self) -> float:
        return round(self.unit_price * self.quantity, 2)


@dataclass(frozen=True, slots=True)
class RawEvent:
    event_type: EventType
    event_timestamp: str
    user_id: str
    session_id: str
    agent_profile: AgentProfile
    city: str
    region: str
    scenario: Scenario
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "event_timestamp": self.event_timestamp,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "agent_profile": self.agent_profile.value,
            "city": self.city,
            "region": self.region,
            "scenario": self.scenario.value,
            "payload": self.payload,
        }


@dataclass(frozen=True, slots=True)
class GeneratedMessage:
    source_hint: SourceHint
    event: RawEvent

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_hint": self.source_hint.value,
            "event": self.event.to_dict(),
        }


@dataclass(slots=True)
class SimulationStats:
    total_events: int = 0
    by_event_type: dict[str, int] = field(default_factory=dict)
    by_profile: dict[str, int] = field(default_factory=dict)
    by_source_hint: dict[str, int] = field(default_factory=dict)

    def register(self, message: GeneratedMessage) -> None:
        self.total_events += 1
        event_type = message.event.event_type.value
        profile = message.event.agent_profile.value
        source = message.source_hint.value
        self.by_event_type[event_type] = self.by_event_type.get(event_type, 0) + 1
        self.by_profile[profile] = self.by_profile.get(profile, 0) + 1
        self.by_source_hint[source] = self.by_source_hint.get(source, 0) + 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_events": self.total_events,
            "by_event_type": dict(sorted(self.by_event_type.items())),
            "by_profile": dict(sorted(self.by_profile.items())),
            "by_source_hint": dict(sorted(self.by_source_hint.items())),
        }
