#!/usr/bin/env python3
"""Crea los topics de contracts/topics.yaml de forma idempotente."""
from __future__ import annotations

import logging

from common import build_parser, client_logger, configure_logging, ensure_root_on_path

ensure_root_on_path()

from confluent_kafka import KafkaException  # noqa: E402
from confluent_kafka.admin import AdminClient, NewTopic  # noqa: E402

from producers.schema import TOPIC_SPECS, TopicPlan, plan_topics  # noqa: E402


LOGGER = logging.getLogger("infra.create_topics")


def fetch_partitions(admin: AdminClient, timeout: float) -> dict[str, int]:
    metadata = admin.list_topics(timeout=timeout)
    return {
        name: len(topic.partitions)
        for name, topic in metadata.topics.items()
        if not name.startswith("_")
    }


def apply_plan(
    admin: AdminClient,
    plan: TopicPlan,
    *,
    replication_factor: int,
    timeout: float,
) -> None:
    new_topics = [
        NewTopic(
            spec.name,
            num_partitions=spec.partitions,
            replication_factor=replication_factor,
        )
        for spec in plan.to_create
    ]
    futures = admin.create_topics(new_topics, request_timeout=timeout)
    for name, future in futures.items():
        future.result(timeout=timeout)
        LOGGER.info("creado %s", name)


def main() -> None:
    parser = build_parser(__doc__ or "")
    parser.add_argument("--replication-factor", type=int, default=1)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra el plan sin tocar el broker",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    configure_logging(args.verbose)

    admin = AdminClient(
        {"bootstrap.servers": args.bootstrap_servers, "logger": client_logger(args.verbose)}
    )
    try:
        existing = fetch_partitions(admin, args.timeout)
    except KafkaException as exc:
        raise SystemExit(f"No se pudo consultar el broker en {args.bootstrap_servers}: {exc}")

    plan = plan_topics(TOPIC_SPECS, existing)

    for spec in plan.unchanged:
        LOGGER.info("sin cambios %s (%d particiones)", spec.name, spec.partitions)

    if plan.has_conflicts:
        for conflict in plan.conflicts:
            LOGGER.error("%s", conflict.describe())
        # Bajar particiones es imposible en Kafka y subirlas rompe el orden por
        # clave de los mensajes ya publicados. Se resuelve con `make reset-b`.
        raise SystemExit("Hay topics que no coinciden con el contrato; no se tocó ninguno")

    if not plan.to_create:
        LOGGER.info("nada que crear: los %d topics ya existen", len(plan.unchanged))
        return

    for spec in plan.to_create:
        LOGGER.info("por crear %s (%d particiones)", spec.name, spec.partitions)

    if args.dry_run:
        LOGGER.info("dry-run: no se creó nada")
        return

    try:
        apply_plan(
            admin,
            plan,
            replication_factor=args.replication_factor,
            timeout=args.timeout,
        )
    except KafkaException as exc:
        raise SystemExit(f"Falló la creación de topics: {exc}")

    LOGGER.info("listo: %d creados, %d sin cambios", len(plan.to_create), len(plan.unchanged))


if __name__ == "__main__":
    main()
