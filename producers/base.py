from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from types import TracebackType
from typing import Any

from confluent_kafka import Producer

from .channels import ChannelConfig, channel_for
from .envelope import (
    build_dead_letter,
    dead_letter_key,
    enrich,
    new_event_id,
    utc_now_iso_ms,
)
from .schema import DEAD_LETTER_TOPIC, Source, topic_for_event
from .validation import ValidationError, validate_event, validate_input


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class Counters:
    publicados: int = 0
    enviados: int = 0
    rechazados: int = 0
    fallidos: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "publicados": self.publicados,
            "enviados": self.enviados,
            "rechazados": self.rechazados,
            "fallidos": self.fallidos,
        }

    def merge(self, other: Counters) -> None:
        self.publicados += other.publicados
        self.enviados += other.enviados
        self.rechazados += other.rechazados
        self.fallidos += other.fallidos


def serialize(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class BaseProducer:
    """Publica los eventos de un canal aplicando la validación en tres pasos.

    Lo que no pasa la validación va al `dead-letter` con el sobre original
    intacto; nunca se descarta en silencio.
    """

    def __init__(
        self,
        *,
        bootstrap: str,
        source: Source | str,
        acks: str = "all",
        extra_config: Mapping[str, Any] | None = None,
    ) -> None:
        self.channel: ChannelConfig = channel_for(source)
        self.counters = Counters()
        config: dict[str, Any] = {
            "bootstrap.servers": bootstrap,
            "client.id": self.channel.client_id,
            "acks": acks,
            "enable.idempotence": True,
            "partitioner": "murmur2_random",
            "linger.ms": self.channel.linger_ms,
            "batch.size": self.channel.batch_size,
            "compression.type": self.channel.compression_type,
        }
        config.update(extra_config or {})
        self._producer = Producer(config)

    @property
    def source(self) -> Source:
        return self.channel.source

    def publish(self, envelope: Any) -> bool:
        """Devuelve True si salió a un topic de negocio, False si fue rechazado."""
        try:
            validate_input(envelope)
            self._check_routing(envelope)
            event = enrich(
                envelope,
                event_id=new_event_id(),
                ingestion_timestamp=utc_now_iso_ms(),
            )
            validate_event(event)
        except ValidationError as exc:
            self.reject(envelope, str(exc))
            return False

        self._produce(
            topic_for_event(event["event_type"]),
            key=event["user_id"],
            value=event,
            dead_letter=False,
        )
        self.counters.publicados += 1
        return True

    def reject(self, original: Any, reason: str) -> None:
        wrapper = build_dead_letter(
            original=original,
            error_reason=reason,
            rejected_at=utc_now_iso_ms(),
        )
        self.counters.rechazados += 1
        LOGGER.debug("rechazado: %s", reason)
        self._produce(
            DEAD_LETTER_TOPIC,
            key=dead_letter_key(original),
            value=wrapper,
            dead_letter=True,
        )

    def flush(self, timeout: float = 30.0) -> int:
        pending = self._producer.flush(timeout)
        if pending:
            LOGGER.error("%s: %d mensajes sin confirmar tras el flush", self.channel.client_id, pending)
        return pending

    def close(self, timeout: float = 30.0) -> int:
        pending = self.flush(timeout)
        LOGGER.info("%s %s", self.channel.client_id, self.counters.to_dict())
        return pending

    def __enter__(self) -> BaseProducer:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        # Salir sin flush descarta el buffer de librdkafka en silencio.
        self.close()

    def _check_routing(self, envelope: Mapping[str, Any]) -> None:
        source_hint = envelope.get("source_hint")
        if source_hint != self.channel.source.value:
            raise ValidationError(
                f"El canal {self.channel.source.value} recibió un evento de {source_hint!r}"
            )

    def _produce(self, topic: str, *, key: str | None, value: Any, dead_letter: bool) -> None:
        encoded_key = key.encode("utf-8") if key is not None else None
        payload = serialize(value)
        try:
            self._producer.produce(
                topic,
                key=encoded_key,
                value=payload,
                on_delivery=self._on_delivery(dead_letter),
            )
        except BufferError:
            # Cola local llena: poll drena acuses y libera espacio.
            self._producer.poll(1.0)
            self._producer.produce(
                topic,
                key=encoded_key,
                value=payload,
                on_delivery=self._on_delivery(dead_letter),
            )
        # poll(0) ejecuta los callbacks ya listos sin bloquear el envío.
        self._producer.poll(0)

    def _on_delivery(self, dead_letter: bool):
        def callback(err: Any, msg: Any) -> None:
            if err is not None:
                self.counters.fallidos += 1
                LOGGER.error("entrega fallida en %s: %s", msg.topic() if msg else "?", err)
                return
            if not dead_letter:
                self.counters.enviados += 1

        return callback
