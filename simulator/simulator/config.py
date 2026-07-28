from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .enums import AgentProfile, Scenario


@dataclass(frozen=True, slots=True)
class ProfileConfig:
    profile: AgentProfile
    population_weight: float
    active_hours: tuple[int, ...]
    delay_min_seconds: float
    delay_max_seconds: float
    offline_delay_min_seconds: float
    offline_delay_max_seconds: float
    min_product_price: float
    max_product_price: float
    preferred_sources: dict[str, float]
    transitions: dict[str, dict[str, float]]
    payment_failure_probability: float


@dataclass(frozen=True, slots=True)
class ScenarioConfig:
    scenario: Scenario
    activity_multiplier: float
    purchase_multiplier: float
    add_to_cart_multiplier: float
    payment_failure_multiplier: float
    discount_by_category: dict[str, float]
    category_boosts: dict[str, float]
    profile_activity_multipliers: dict[str, float]
    background_event_weights: dict[str, float]


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    agents: int
    duration_real_seconds: float
    virtual_start: str
    speed_factor: float
    seed: int
    output_dir: str
    console_sample_limit: int
    background_interval_min_seconds: float
    background_interval_max_seconds: float


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo de configuración: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"El YAML debe contener un objeto: {path}")
    return data


def load_simulation_config(path: Path) -> SimulationConfig:
    raw = _load_yaml(path)["simulation"]
    return SimulationConfig(
        agents=int(raw["agents"]),
        duration_real_seconds=float(raw["duration_real_seconds"]),
        virtual_start=str(raw["virtual_start"]),
        speed_factor=float(raw["speed_factor"]),
        seed=int(raw["seed"]),
        output_dir=str(raw["output_dir"]),
        console_sample_limit=int(raw.get("console_sample_limit", 20)),
        background_interval_min_seconds=float(raw.get("background_interval_min_seconds", 0.25)),
        background_interval_max_seconds=float(raw.get("background_interval_max_seconds", 0.80)),
    )


def load_profiles(path: Path) -> dict[AgentProfile, ProfileConfig]:
    raw = _load_yaml(path)["profiles"]
    profiles: dict[AgentProfile, ProfileConfig] = {}
    for name, values in raw.items():
        profile = AgentProfile(name)
        profiles[profile] = ProfileConfig(
            profile=profile,
            population_weight=float(values["population_weight"]),
            active_hours=tuple(int(hour) for hour in values["active_hours"]),
            delay_min_seconds=float(values["delay_seconds"][0]),
            delay_max_seconds=float(values["delay_seconds"][1]),
            offline_delay_min_seconds=float(values["offline_delay_seconds"][0]),
            offline_delay_max_seconds=float(values["offline_delay_seconds"][1]),
            min_product_price=float(values["product_price_range"][0]),
            max_product_price=float(values["product_price_range"][1]),
            preferred_sources={str(k): float(v) for k, v in values["preferred_sources"].items()},
            transitions={
                str(state): {str(action): float(weight) for action, weight in actions.items()}
                for state, actions in values["transitions"].items()
            },
            payment_failure_probability=float(values.get("payment_failure_probability", 0.05)),
        )
    missing = set(AgentProfile) - set(profiles)
    if missing:
        raise ValueError(f"Faltan perfiles en profiles.yaml: {sorted(p.value for p in missing)}")
    return profiles


def load_scenario(base_path: Path, scenario_path: Path) -> ScenarioConfig:
    base = _load_yaml(base_path)["scenario"]
    override = _load_yaml(scenario_path)["scenario"]

    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value

    return ScenarioConfig(
        scenario=Scenario(str(merged["name"])),
        activity_multiplier=float(merged["activity_multiplier"]),
        purchase_multiplier=float(merged["purchase_multiplier"]),
        add_to_cart_multiplier=float(merged["add_to_cart_multiplier"]),
        payment_failure_multiplier=float(merged["payment_failure_multiplier"]),
        discount_by_category={str(k): float(v) for k, v in merged.get("discount_by_category", {}).items()},
        category_boosts={str(k): float(v) for k, v in merged.get("category_boosts", {}).items()},
        profile_activity_multipliers={
            str(k): float(v) for k, v in merged.get("profile_activity_multipliers", {}).items()
        },
        background_event_weights={
            str(k): float(v) for k, v in merged.get("background_event_weights", {}).items()
        },
    )
