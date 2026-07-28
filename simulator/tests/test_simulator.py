from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from simulator.config import load_profiles, load_scenario, load_simulation_config
from simulator.engine import SimulationEngine
from simulator.enums import AgentProfile, EventType
from simulator.validation import PAYLOAD_REQUIRED_FIELDS


ROOT = Path(__file__).resolve().parents[1]


class SimulatorTests(unittest.TestCase):
    def test_all_eight_profiles_are_configured(self) -> None:
        profiles = load_profiles(ROOT / "configs" / "profiles.yaml")
        self.assertEqual(set(profiles), set(AgentProfile))

    def test_all_twelve_payload_contracts_exist(self) -> None:
        self.assertEqual(set(PAYLOAD_REQUIRED_FIELDS), set(EventType))

    def test_smoke_simulation_writes_valid_jsonl(self) -> None:
        simulation = load_simulation_config(ROOT / "configs" / "simulation.yaml")
        profiles = load_profiles(ROOT / "configs" / "profiles.yaml")
        scenario = load_scenario(
            ROOT / "configs" / "scenarios" / "base.yaml",
            ROOT / "configs" / "scenarios" / "black_friday.yaml",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = SimulationEngine(
                root_dir=ROOT,
                simulation=simulation,
                profiles=profiles,
                scenario=scenario,
                agents_override=16,
                duration_override=0.8,
                speed_override=7200,
                output_override=temp_dir,
                console_enabled=False,
            )
            result = asyncio.run(engine.run())
            self.assertGreater(result["stats"]["total_events"], 0)
            events_path = Path(result["output_dir"]) / "events.jsonl"
            first_line = events_path.read_text(encoding="utf-8").splitlines()[0]
            record = json.loads(first_line)
            self.assertIn("source_hint", record)
            self.assertIn("event", record)
            self.assertNotIn("event_id", record["event"])
            self.assertNotIn("ingestion_timestamp", record["event"])
            self.assertNotIn("source", record["event"])

    def test_zero_overrides_are_rejected_instead_of_ignored(self) -> None:
        simulation = load_simulation_config(ROOT / "configs" / "simulation.yaml")
        profiles = load_profiles(ROOT / "configs" / "profiles.yaml")
        scenario = load_scenario(
            ROOT / "configs" / "scenarios" / "base.yaml",
            ROOT / "configs" / "scenarios" / "base.yaml",
        )
        engine = SimulationEngine(
            root_dir=ROOT,
            simulation=simulation,
            profiles=profiles,
            scenario=scenario,
            agents_override=0,
            console_enabled=False,
        )
        with self.assertRaisesRegex(ValueError, "agentes"):
            asyncio.run(engine.run())

    def test_background_task_errors_are_propagated(self) -> None:
        simulation = replace(
            load_simulation_config(ROOT / "configs" / "simulation.yaml"),
            background_interval_min_seconds=0.001,
            background_interval_max_seconds=0.001,
        )
        profiles = load_profiles(ROOT / "configs" / "profiles.yaml")
        scenario = replace(
            load_scenario(
                ROOT / "configs" / "scenarios" / "base.yaml",
                ROOT / "configs" / "scenarios" / "base.yaml",
            ),
            background_event_weights={"EVENTO_INVALIDO": 1.0},
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = SimulationEngine(
                root_dir=ROOT,
                simulation=simulation,
                profiles=profiles,
                scenario=scenario,
                agents_override=2,
                duration_override=0.05,
                output_override=temp_dir,
                console_enabled=False,
            )
            with self.assertRaisesRegex(RuntimeError, "tarea de simulación"):
                asyncio.run(engine.run())


if __name__ == "__main__":
    unittest.main()
