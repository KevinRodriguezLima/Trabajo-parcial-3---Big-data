from __future__ import annotations

import asyncio
import random
from datetime import datetime
from pathlib import Path

from .agent import Agent
from .background import BackgroundEventGenerator
from .catalog import Catalog
from .clock import VirtualClock
from .config import ProfileConfig, ScenarioConfig, SimulationConfig
from .enums import AgentProfile
from .sinks import CompositeSink, ConsoleSink, JsonlDirectorySink


class SimulationEngine:
    def __init__(
        self,
        *,
        root_dir: Path,
        simulation: SimulationConfig,
        profiles: dict[AgentProfile, ProfileConfig],
        scenario: ScenarioConfig,
        agents_override: int | None = None,
        duration_override: float | None = None,
        speed_override: float | None = None,
        output_override: str | None = None,
        console_enabled: bool = True,
    ) -> None:
        self.root_dir = root_dir
        self.simulation = simulation
        self.profiles = profiles
        self.scenario = scenario
        self.agents_count = (
            agents_override if agents_override is not None else simulation.agents
        )
        self.duration = (
            duration_override
            if duration_override is not None
            else simulation.duration_real_seconds
        )
        self.speed = speed_override if speed_override is not None else simulation.speed_factor
        output_name = output_override if output_override is not None else simulation.output_dir
        self.output_dir = root_dir / output_name / scenario.scenario.value.lower()
        self.console_enabled = console_enabled

    async def run(self) -> dict:
        if self.agents_count <= 0:
            raise ValueError("La cantidad de agentes debe ser mayor que cero")
        if self.duration <= 0:
            raise ValueError("La duración debe ser mayor que cero")

        catalog = Catalog(
            self.root_dir / "data" / "products.json",
            self.root_dir / "data" / "locations.json",
        )
        start_virtual = datetime.fromisoformat(self.simulation.virtual_start)
        clock = VirtualClock(start_virtual=start_virtual, speed_factor=self.speed)

        file_sink = JsonlDirectorySink(self.output_dir)
        sinks = [file_sink]
        if self.console_enabled:
            sinks.append(ConsoleSink(self.simulation.console_sample_limit))
        sink = CompositeSink(*sinks)

        agents = self._create_agents(catalog, clock, sink)
        background = BackgroundEventGenerator(
            agents=agents,
            catalog=catalog,
            clock=clock,
            scenario=self.scenario,
            simulation=self.simulation,
            sink=sink,
            seed=self.simulation.seed + 900_000,
        )

        stop_event = asyncio.Event()
        tasks = [asyncio.create_task(agent.run(stop_event)) for agent in agents]
        tasks.append(asyncio.create_task(background.run(stop_event)))

        try:
            await asyncio.sleep(self.duration)
        finally:
            stop_event.set()
            for task in tasks:
                task.cancel()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            await sink.close()

        failures = [
            result
            for result in results
            if isinstance(result, BaseException)
            and not isinstance(result, asyncio.CancelledError)
        ]
        if failures:
            raise RuntimeError("Una tarea de simulación terminó con error") from failures[0]

        return {
            "scenario": self.scenario.scenario.value,
            "agents": self.agents_count,
            "duration_real_seconds": self.duration,
            "speed_factor": self.speed,
            "virtual_start": start_virtual.isoformat(),
            "virtual_end": clock.now().isoformat(timespec="milliseconds"),
            "output_dir": str(self.output_dir),
            "stats": file_sink.stats.to_dict(),
        }

    def _create_agents(self, catalog: Catalog, clock: VirtualClock, sink: CompositeSink) -> list[Agent]:
        rng = random.Random(self.simulation.seed)
        profile_list = list(self.profiles.values())
        weights = [profile.population_weight for profile in profile_list]
        selected_profiles = rng.choices(profile_list, weights=weights, k=self.agents_count)
        return [
            Agent(
                user_id=f"USR{index:06d}",
                profile=profile,
                scenario=self.scenario,
                catalog=catalog,
                clock=clock,
                sink=sink,
                seed=self.simulation.seed + index * 7919,
            )
            for index, profile in enumerate(selected_profiles, start=1)
        ]
