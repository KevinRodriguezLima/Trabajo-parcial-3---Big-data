#!/usr/bin/env python3
"""Publica y consume un evento por topic, y verifica el particionado por user_id."""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from common import (
    build_parser,
    client_logger,
    configure_logging,
    ensure_root_on_path,
    load_env_file,
)

ensure_root_on_path()

from confluent_kafka import Consumer, KafkaError, KafkaException, Producer  # noqa: E402

from producers.envelope import (  # noqa: E402
    build_dead_letter,
    dead_letter_key,
    enrich,
    new_event_id,
    utc_now_iso_ms,
)
from producers.partitioning import partition_for_key  # noqa: E402
from producers.schema import (  # noqa: E402
    DEAD_LETTER_TOPIC,
    TOPIC_SPECS,
    EventType,
    Source,
    load_required_fields,
    partitions_by_topic,
    topic_for_event,
)


LOGGER = logging.getLogger("infra.smoke_test")

# Un event_type por cada topic de negocio, con el payload mínimo del contrato.
FIXTURES: tuple[tuple[EventType, Source, dict[str, Any]], ...] = (
    (EventType.LOGIN, Source.MOBILE, {"device": "MOBILE_IOS", "is_first_login": True}),
    (
        EventType.PURCHASE,
        Source.WEB,
        {
            "order_id": "ORD_SMOKE_00001",
            "cart_id": "CART_SMOKE_0001",
            "items": [
                {
                    "product_id": "P042",
                    "product_name": "Laptop Lenovo IdeaPad 3",
                    "category": "TECNOLOGIA",
                    "unit_price": 3499.9,
                    "quantity": 1,
                    "subtotal": 3499.9,
                }
            ],
            "items_count": 1,
            "total_units": 1,
            "total_amount": 3499.9,
            "currency": "PEN",
            "payment_method": "YAPE",
            "time_to_purchase_ms": 142000,
        },
    ),
    (
        EventType.GPS_UPDATE,
        Source.VEHICLE,
        {
            "device_id": "DEV_5495",
            "latitude": -16.413598,
            "longitude": -71.530629,
            "speed_kmh": 24.1,
        },
    ),
    (
        EventType.SOCIAL_POST,
        Source.WEB,
        {
            "platform": "FACEBOOK",
            "post_type": "COMMENT",
            "product_id": "P006",
            "sentiment": "POSITIVE",
        },
    ),
)

USER_IDS: tuple[str, ...] = (
    "USR000012",
    "USR000030",
    "USR000065",
    "USR000096",
    "USR000119",
    "USR000254",
)

# Tiempo de evento fijo, en -05:00 como el reloj virtual de A: hace evidente
# que ingestion_timestamp (UTC, real) es otra cosa.
EVENT_TIMESTAMP = "2026-07-25T18:00:15.928-05:00"


@dataclass(slots=True)
class Delivery:
    event_id: str
    topic: str
    key: str | None
    expected_partition: int | None
    partition: int | None = None
    offset: int | None = None
    error: str | None = None


@dataclass(slots=True)
class Report:
    produced: int = 0
    deliveries: list[Delivery] = field(default_factory=list)
    consumed: set[str] = field(default_factory=set)
    problems: list[str] = field(default_factory=list)

    @property
    def confirmed(self) -> int:
        # Confirmado es haber recibido acuse con partición, no la ausencia de
        # error: un mensaje que nunca llegó al broker tampoco tiene error.
        return sum(
            1
            for delivery in self.deliveries
            if delivery.error is None and delivery.partition is not None
        )


def build_envelope(event_type: EventType, source: Source, user_id: str, payload: dict) -> dict:
    return {
        "source_hint": source.value,
        "event": {
            "event_type": event_type.value,
            "event_timestamp": EVENT_TIMESTAMP,
            "user_id": user_id,
            "session_id": f"SES_{user_id}_0001",
            "agent_profile": "CLIENTE_FRECUENTE",
            "city": "Arequipa",
            "region": "AREQUIPA",
            "scenario": "BASE",
            "payload": payload,
        },
    }


def producer_config(bootstrap: str, verbose: bool) -> dict[str, Any]:
    load_env_file()
    return {
        "bootstrap.servers": bootstrap,
        "logger": client_logger(verbose),
        "acks": os.environ.get("PRODUCER_ACKS", "all"),
        "enable.idempotence": os.environ.get("PRODUCER_ENABLE_IDEMPOTENCE", "true"),
        "compression.type": os.environ.get("PRODUCER_COMPRESSION_TYPE", "lz4"),
        "linger.ms": int(os.environ.get("PRODUCER_LINGER_MS", "10")),
        "batch.size": int(os.environ.get("PRODUCER_BATCH_SIZE", "131072")),
        "partitioner": os.environ.get("PRODUCER_PARTITIONER", "murmur2_random"),
    }


def serialize(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def publish(producer: Producer, report: Report, run_id: str) -> None:
    partitions = partitions_by_topic(TOPIC_SPECS)
    required = set(load_required_fields())

    for event_type, source, payload in FIXTURES:
        topic = topic_for_event(event_type)
        for user_id in USER_IDS:
            envelope = build_envelope(event_type, source, user_id, payload)
            event = enrich(
                envelope,
                event_id=new_event_id(),
                ingestion_timestamp=utc_now_iso_ms(),
            )
            if set(event) != required:
                report.problems.append(
                    f"{event_type.value}: el evento publicado no tiene los 13 campos del contrato"
                )
            delivery = Delivery(
                event_id=event["event_id"],
                topic=topic,
                key=user_id,
                expected_partition=partition_for_key(user_id, partitions[topic]),
            )
            report.deliveries.append(delivery)
            report.produced += 1
            producer.produce(
                topic,
                key=user_id.encode("utf-8"),
                value=serialize(event),
                on_delivery=_callback(delivery),
            )
            # poll(0) sirve los callbacks ya encolados sin bloquear el envío.
            producer.poll(0)

    original = build_envelope(EventType.LOGIN, Source.WEB, "USR000030", {"device": "WEB_DESKTOP"})
    del original["event"]["user_id"]
    wrapper = build_dead_letter(
        original=original,
        error_reason=f"prueba de humo {run_id}: payload incompleto y sin user_id",
        rejected_at=utc_now_iso_ms(),
    )
    key = dead_letter_key(original)
    delivery = Delivery(
        event_id=f"dlq_{run_id}",
        topic=DEAD_LETTER_TOPIC,
        key=key,
        expected_partition=None,
    )
    report.deliveries.append(delivery)
    report.produced += 1
    producer.produce(
        DEAD_LETTER_TOPIC,
        key=key.encode("utf-8") if key is not None else None,
        value=serialize(wrapper),
        on_delivery=_callback(delivery),
    )


def _callback(delivery: Delivery):
    def on_delivery(err: KafkaError | None, msg: Any) -> None:
        if err is not None:
            delivery.error = str(err)
            return
        delivery.partition = msg.partition()
        delivery.offset = msg.offset()

    return on_delivery


def verify_deliveries(report: Report) -> None:
    for delivery in report.deliveries:
        if delivery.error is not None:
            report.problems.append(f"{delivery.topic}: entrega fallida ({delivery.error})")
            continue
        if delivery.partition is None:
            report.problems.append(f"{delivery.topic}: sin acuse de entrega")
            continue
        if delivery.expected_partition is None:
            continue
        if delivery.partition != delivery.expected_partition:
            report.problems.append(
                f"{delivery.topic}: la clave {delivery.key} cayó en la partición "
                f"{delivery.partition} y el particionador esperaba "
                f"{delivery.expected_partition}"
            )


def consume(bootstrap: str, report: Report, run_id: str, timeout: float, verbose: bool) -> None:
    expected = {delivery.event_id for delivery in report.deliveries}
    consumer = Consumer(
        {
            "bootstrap.servers": bootstrap,
            "logger": client_logger(verbose),
            "group.id": f"smoke-{run_id}",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([spec.name for spec in TOPIC_SPECS])
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline and not expected <= report.consumed:
            message = consumer.poll(1.0)
            if message is None:
                continue
            if message.error():
                LOGGER.debug("poll: %s", message.error())
                continue
            payload = json.loads(message.value().decode("utf-8"))
            identifier = payload.get("event_id")
            if identifier is None and run_id in str(payload.get("error_reason", "")):
                identifier = f"dlq_{run_id}"
            if identifier in expected:
                report.consumed.add(identifier)
    finally:
        consumer.close()

    missing = expected - report.consumed
    if missing:
        report.problems.append(f"No se consumieron {len(missing)} de {len(expected)} mensajes")


def render(report: Report) -> str:
    by_topic: dict[str, list[Delivery]] = {}
    for delivery in report.deliveries:
        by_topic.setdefault(delivery.topic, []).append(delivery)

    lines = [
        f"{'TOPIC':<16}{'PUBLICADOS':>11}{'CONFIRMADOS':>12}   PARTICIONES USADAS",
    ]
    for topic, deliveries in by_topic.items():
        confirmed = [d for d in deliveries if d.error is None and d.partition is not None]
        used = sorted({d.partition for d in confirmed})
        lines.append(f"{topic:<16}{len(deliveries):>11}{len(confirmed):>12}   {used}")

    lines.append("")
    lines.append(f"{'CLAVE':<12}{'TOPIC':<16}{'ESPERADA':>9}{'REAL':>6}")
    for delivery in report.deliveries:
        if delivery.expected_partition is None:
            continue
        lines.append(
            f"{str(delivery.key):<12}{delivery.topic:<16}"
            f"{delivery.expected_partition:>9}{str(delivery.partition):>6}"
        )

    lines.append("")
    lines.append(
        f"publicados={report.produced} confirmados={report.confirmed} "
        f"consumidos={len(report.consumed)}"
    )
    return "\n".join(lines)


def main() -> None:
    parser = build_parser(__doc__ or "")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    configure_logging(args.verbose)

    run_id = uuid4().hex[:8]
    report = Report()
    producer = Producer(producer_config(args.bootstrap_servers, args.verbose))

    try:
        publish(producer, report, run_id)
        pending = producer.flush(args.timeout)
    except KafkaException as exc:
        raise SystemExit(f"No se pudo publicar en {args.bootstrap_servers}: {exc}")

    if pending:
        report.problems.append(f"flush dejó {pending} mensajes sin confirmar")

    verify_deliveries(report)
    consume(args.bootstrap_servers, report, run_id, args.timeout, args.verbose)

    print(render(report))

    if report.problems:
        for problem in report.problems:
            LOGGER.error("%s", problem)
        raise SystemExit(f"Prueba de humo fallida: {len(report.problems)} problemas")

    LOGGER.info("prueba de humo correcta")


if __name__ == "__main__":
    main()
