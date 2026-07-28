#!/usr/bin/env python3
"""Compara los topics reales del broker contra contracts/topics.yaml."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from common import build_parser, client_logger, configure_logging, ensure_root_on_path

ensure_root_on_path()

from confluent_kafka import KafkaException  # noqa: E402
from confluent_kafka.admin import AdminClient  # noqa: E402

from producers.schema import TOPIC_BY_EVENT, TOPIC_SPECS, plan_topics  # noqa: E402


LOGGER = logging.getLogger("infra.describe_topics")


def collect(admin: AdminClient, timeout: float) -> dict[str, Any]:
    metadata = admin.list_topics(timeout=timeout)
    existing = {
        name: len(topic.partitions)
        for name, topic in metadata.topics.items()
        if not name.startswith("_")
    }
    plan = plan_topics(TOPIC_SPECS, existing)

    topics: list[dict[str, Any]] = []
    for spec in TOPIC_SPECS:
        topic = metadata.topics.get(spec.name)
        partitions = [
            {
                "id": partition.id,
                "leader": partition.leader,
                "replicas": list(partition.replicas),
                "isrs": list(partition.isrs),
            }
            for partition in sorted(topic.partitions.values(), key=lambda item: item.id)
        ] if topic is not None else []
        topics.append(
            {
                "name": spec.name,
                "expected_partitions": spec.partitions,
                "actual_partitions": len(partitions),
                "state": _state(spec.name, plan),
                "event_types": [event_type.value for event_type in spec.event_types],
                "partitions": partitions,
            }
        )

    return {
        "bootstrap_servers": [str(broker) for broker in metadata.brokers.values()],
        "topics": topics,
        "routing": {
            event_type.value: topic for event_type, topic in sorted(TOPIC_BY_EVENT.items())
        },
        "matches_contract": not plan.has_conflicts and not plan.to_create,
    }


def _state(name: str, plan: Any) -> str:
    if any(spec.name == name for spec in plan.to_create):
        return "FALTA"
    if any(conflict.name == name for conflict in plan.conflicts):
        return "DISCREPA"
    return "OK"


def render(report: dict[str, Any]) -> str:
    lines = [
        f"Brokers: {', '.join(report['bootstrap_servers'])}",
        "",
        f"{'TOPIC':<16}{'CONTRATO':>9}{'REAL':>6}{'ESTADO':>10}   EVENT_TYPES",
    ]
    for topic in report["topics"]:
        event_types = ", ".join(topic["event_types"]) or "-"
        lines.append(
            f"{topic['name']:<16}"
            f"{topic['expected_partitions']:>9}"
            f"{topic['actual_partitions']:>6}"
            f"{topic['state']:>10}   {event_types}"
        )
    lines.append("")
    for topic in report["topics"]:
        for partition in topic["partitions"]:
            lines.append(
                f"  {topic['name']}[{partition['id']}] "
                f"líder={partition['leader']} "
                f"réplicas={partition['replicas']} isr={partition['isrs']}"
            )
    return "\n".join(lines)


def main() -> None:
    parser = build_parser(__doc__ or "")
    parser.add_argument("--json", type=Path, help="Guarda el reporte como evidencia")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    configure_logging(args.verbose)

    admin = AdminClient(
        {"bootstrap.servers": args.bootstrap_servers, "logger": client_logger(args.verbose)}
    )
    try:
        report = collect(admin, args.timeout)
    except KafkaException as exc:
        raise SystemExit(f"No se pudo consultar el broker en {args.bootstrap_servers}: {exc}")

    print(render(report))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        LOGGER.info("reporte escrito en %s", args.json)

    if not report["matches_contract"]:
        raise SystemExit("El broker no coincide con contracts/topics.yaml")


if __name__ == "__main__":
    main()
