#!/usr/bin/env python3
"""Consume los topics de negocio y guarda cada evento en PostgreSQL."""
from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from types import FrameType
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg  # noqa: E402
from confluent_kafka import Consumer, KafkaException  # noqa: E402

from producers.schema import BUSINESS_TOPICS  # noqa: E402
from producers.store import INSERT_EVENTS, Batch, dsn_from_env, row_from_event  # noqa: E402


LOGGER = logging.getLogger("producers.consumer_store")
DEFAULT_BOOTSTRAP = "localhost:29092"
# Grupo propio: el de Flink debe ser otro para que ambos lean todo el flujo.
DEFAULT_GROUP_ID = "event-store"


@dataclass(slots=True)
class Counters:
    leidos: int = 0
    insertados: int = 0
    duplicados: int = 0
    invalidos: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "leidos": self.leidos,
            "insertados": self.insertados,
            "duplicados": self.duplicados,
            "invalidos": self.invalidos,
        }


@dataclass(slots=True)
class Stopper:
    stopping: bool = False

    def request(self, signum: int, frame: FrameType | None) -> None:
        LOGGER.info("señal %s recibida: se vacía el lote pendiente y se cierra", signum)
        self.stopping = True


def write_batch(
    connection: psycopg.Connection,
    consumer: Consumer,
    batch: Batch,
    counters: Counters,
) -> None:
    """Escribe el lote y solo entonces confirma los offsets."""
    rows = batch.drain()
    if not rows:
        return
    with connection.cursor() as cursor:
        cursor.executemany(INSERT_EVENTS, rows)
        insertados = cursor.rowcount if cursor.rowcount is not None and cursor.rowcount >= 0 else 0
    connection.commit()
    # El commit de offsets va después de la escritura: si el proceso muere en
    # medio, se reprocesa y ON CONFLICT descarta lo que ya estaba.
    consumer.commit(asynchronous=False)
    counters.insertados += insertados
    counters.duplicados += len(rows) - insertados
    LOGGER.info("lote de %d filas: %d nuevas", len(rows), insertados)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap", default=DEFAULT_BOOTSTRAP)
    parser.add_argument("--dsn", default=None, help="DSN de PostgreSQL")
    parser.add_argument("--group-id", default=DEFAULT_GROUP_ID)
    parser.add_argument("--topics", nargs="+", default=list(BUSINESS_TOPICS))
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--batch-seconds", type=float, default=2.0)
    parser.add_argument("--verbose", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
        stream=sys.stderr,
    )

    stopper = Stopper()
    signal.signal(signal.SIGINT, stopper.request)
    signal.signal(signal.SIGTERM, stopper.request)

    counters = Counters()
    batch = Batch(max_rows=args.batch_size, max_seconds=args.batch_seconds)
    consumer = Consumer(
        {
            "bootstrap.servers": args.bootstrap,
            "group.id": args.group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )

    try:
        connection = psycopg.connect(args.dsn or dsn_from_env(), connect_timeout=10)
    except psycopg.Error as exc:
        consumer.close()
        raise SystemExit(f"No se pudo conectar a PostgreSQL: {exc}")

    consumer.subscribe(args.topics)
    LOGGER.info("grupo %s escuchando %s", args.group_id, ", ".join(args.topics))

    try:
        while not stopper.stopping:
            message = consumer.poll(0.5)
            if message is not None:
                _absorb(message, batch, counters)
            if batch.should_flush(time.monotonic()):
                write_batch(connection, consumer, batch, counters)
        write_batch(connection, consumer, batch, counters)
    except KafkaException as exc:
        raise SystemExit(f"Error de Kafka: {exc}")
    finally:
        consumer.close()
        connection.close()

    print(json.dumps(counters.to_dict(), ensure_ascii=False, indent=2))


def _absorb(message: Any, batch: Batch, counters: Counters) -> None:
    if message.error():
        LOGGER.debug("poll: %s", message.error())
        return
    counters.leidos += 1
    try:
        event = json.loads(message.value().decode("utf-8"))
        row = row_from_event(
            event,
            topic=message.topic(),
            partition=message.partition(),
            offset=message.offset(),
        )
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError) as exc:
        counters.invalidos += 1
        LOGGER.warning(
            "mensaje ilegible en %s[%d]@%d: %s",
            message.topic(),
            message.partition(),
            message.offset(),
            exc,
        )
        return
    batch.add(row, time.monotonic())


if __name__ == "__main__":
    main()
