from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .config import load_profiles, load_scenario, load_simulation_config
from .engine import SimulationEngine
from .enums import Scenario


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Simulador de agentes para audiencias digitales en tiempo real"
    )
    parser.add_argument(
        "--scenario",
        default="BASE",
        choices=[scenario.value for scenario in Scenario],
        help="Escenario empresarial que modifica el comportamiento",
    )
    parser.add_argument("--agents", type=int, help="Sobrescribe la cantidad de agentes")
    parser.add_argument("--duration", type=float, help="Duración real en segundos")
    parser.add_argument("--speed", type=float, help="Segundos virtuales por segundo real")
    parser.add_argument("--output", help="Directorio base de salida")
    parser.add_argument(
        "--no-console",
        action="store_true",
        help="No mostrar eventos de muestra en la consola",
    )
    return parser


async def async_main(args: argparse.Namespace) -> None:
    root = Path(__file__).resolve().parents[1]
    simulation = load_simulation_config(root / "configs" / "simulation.yaml")
    profiles = load_profiles(root / "configs" / "profiles.yaml")
    scenario_name = args.scenario.lower()
    scenario = load_scenario(
        root / "configs" / "scenarios" / "base.yaml",
        root / "configs" / "scenarios" / f"{scenario_name}.yaml",
    )
    engine = SimulationEngine(
        root_dir=root,
        simulation=simulation,
        profiles=profiles,
        scenario=scenario,
        agents_override=args.agents,
        duration_override=args.duration,
        speed_override=args.speed,
        output_override=args.output,
        console_enabled=not args.no_console,
    )
    result = await engine.run()
    print("\n=== RESUMEN DE SIMULACIÓN ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    args = build_parser().parse_args()
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
