from __future__ import annotations

import asyncio
import random

from .agent import Agent
from .catalog import Catalog
from .clock import VirtualClock
from .config import ScenarioConfig, SimulationConfig
from .enums import EventType, SourceHint
from .event_factory import EventFactory
from .policy import weighted_choice
from .sinks import EventSink


class BackgroundEventGenerator:
    def __init__(
        self,
        *,
        agents: list[Agent],
        catalog: Catalog,
        clock: VirtualClock,
        scenario: ScenarioConfig,
        simulation: SimulationConfig,
        sink: EventSink,
        seed: int,
    ) -> None:
        self.agents = agents
        self.catalog = catalog
        self.clock = clock
        self.scenario = scenario
        self.simulation = simulation
        self.sink = sink
        self.rng = random.Random(seed)
        self.factory = EventFactory(catalog, scenario, self.rng)

    async def run(self, stop_event: asyncio.Event) -> None:
        if not self.scenario.background_event_weights:
            return
        while not stop_event.is_set():
            await asyncio.sleep(
                self.rng.uniform(
                    self.simulation.background_interval_min_seconds,
                    self.simulation.background_interval_max_seconds,
                )
                / max(self.scenario.activity_multiplier, 0.1)
            )
            agent = self.rng.choice(self.agents)
            event_name = weighted_choice(self.rng, self.scenario.background_event_weights)
            event_type = EventType(event_name)
            source_hint, payload = self._payload(event_type, agent)
            message = self.factory.build(
                event_type=event_type,
                event_time=self.clock.now(),
                user_id=agent.user_id,
                session_id=agent.current_session_id,
                profile=agent.profile.profile,
                location=agent.location,
                source_hint=source_hint,
                payload=payload,
            )
            await self.sink.emit(message)

    def _payload(self, event_type: EventType, agent: Agent) -> tuple[SourceHint, dict]:
        if event_type == EventType.GPS_UPDATE:
            return SourceHint.VEHICLE, self.factory.gps_payload(agent.location)
        if event_type == EventType.IOT_READING:
            return SourceHint.IOT, self.factory.iot_payload()
        if event_type == EventType.MOTION_DETECTED:
            return SourceHint.IOT, self.factory.motion_payload()
        if event_type == EventType.SOCIAL_POST:
            product = self.catalog.choose_product(
                self.rng,
                self.scenario,
                0.0,
                float("inf"),
            )
            return self.rng.choice([SourceHint.WEB, SourceHint.MOBILE]), self.factory.social_payload(product)
        raise ValueError(f"Evento de fondo no soportado: {event_type.value}")
