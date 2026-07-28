#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from simulator.enums import AgentProfile, EventType, Scenario
from simulator.models import RawEvent
from simulator.validation import validate_raw_event


def main() -> None:
    parser = argparse.ArgumentParser(description="Valida el JSONL generado por la parte A")
    parser.add_argument("path", type=Path, help="Ruta a events.jsonl")
    args = parser.parse_args()

    if not args.path.exists():
        raise SystemExit(f"No existe: {args.path}")

    total = 0
    errors: list[str] = []
    with args.path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            total += 1
            try:
                wrapper = json.loads(line)
                raw = wrapper["event"]
                event = RawEvent(
                    event_type=EventType(raw["event_type"]),
                    event_timestamp=raw["event_timestamp"],
                    user_id=raw["user_id"],
                    session_id=raw["session_id"],
                    agent_profile=AgentProfile(raw["agent_profile"]),
                    city=raw["city"],
                    region=raw["region"],
                    scenario=Scenario(raw["scenario"]),
                    payload=raw["payload"],
                )
                validate_raw_event(event)
            except Exception as exc:  # noqa: BLE001 - herramienta de validación
                errors.append(f"Línea {line_number}: {exc}")

    if errors:
        print(f"Se encontraron {len(errors)} errores de {total} eventos")
        for error in errors[:20]:
            print("-", error)
        raise SystemExit(1)
    print(f"OK: {total} eventos válidos según los campos y payloads de la parte A")


if __name__ == "__main__":
    main()
