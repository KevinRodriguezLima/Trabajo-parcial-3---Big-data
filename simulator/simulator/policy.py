from __future__ import annotations

import random
from collections.abc import Mapping

from .config import ProfileConfig, ScenarioConfig
from .enums import AgentProfile, SourceHint


def weighted_choice(rng: random.Random, weights: Mapping[str, float]) -> str:
    positive = [(key, value) for key, value in weights.items() if value > 0]
    if not positive:
        raise ValueError("La política no contiene opciones con peso positivo")
    keys, values = zip(*positive)
    return rng.choices(keys, weights=values, k=1)[0]


def choose_source(rng: random.Random, profile: ProfileConfig) -> SourceHint:
    selected = weighted_choice(rng, profile.preferred_sources)
    return SourceHint(selected)


def profile_activity_multiplier(profile: AgentProfile, scenario: ScenarioConfig) -> float:
    return scenario.profile_activity_multipliers.get(profile.value, 1.0)


def adjusted_actions(
    profile: ProfileConfig,
    scenario: ScenarioConfig,
    state_name: str,
) -> dict[str, float]:
    actions = dict(profile.transitions[state_name])
    if "PURCHASE" in actions:
        actions["PURCHASE"] *= scenario.purchase_multiplier
    if "ADD_TO_CART" in actions:
        actions["ADD_TO_CART"] *= scenario.add_to_cart_multiplier

    if profile.profile == AgentProfile.CLIENTE_ESTACIONAL:
        if scenario.scenario.value == "BASE":
            if "PURCHASE" in actions:
                actions["PURCHASE"] *= 0.25
            if "ADD_TO_CART" in actions:
                actions["ADD_TO_CART"] *= 0.50
        else:
            if "PURCHASE" in actions:
                actions["PURCHASE"] *= 2.4
            if "ADD_TO_CART" in actions:
                actions["ADD_TO_CART"] *= 1.8
    return actions
