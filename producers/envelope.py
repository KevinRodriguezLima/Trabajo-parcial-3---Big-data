from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .schema import SCHEMA_VERSION, SOURCE_FIELDS, Source


def new_event_id() -> str:
    return f"evt_{uuid4().hex}"


def utc_now_iso_ms() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def enrich(
    envelope: Mapping[str, Any],
    *,
    event_id: str,
    ingestion_timestamp: str,
) -> dict[str, Any]:
    """Desarma el sobre de A y devuelve el evento plano de 13 campos.

    Los dos valores no deterministas se inyectan para que la función sea pura.
    """
    event = envelope.get("event")
    if not isinstance(event, Mapping):
        raise TypeError("El sobre debe traer un objeto 'event'")

    missing = [field for field in SOURCE_FIELDS if field not in event]
    if missing:
        raise ValueError(f"El sobre no trae los campos de A: {missing}")

    source_hint = envelope.get("source_hint")
    try:
        source = Source(source_hint)
    except ValueError as exc:
        raise ValueError(f"source_hint fuera del contrato: {source_hint!r}") from exc

    return {
        "event_id": event_id,
        "schema_version": SCHEMA_VERSION,
        **{field: event[field] for field in SOURCE_FIELDS},
        "ingestion_timestamp": ingestion_timestamp,
        "source": source.value,
    }


def build_dead_letter(
    *,
    original: Any,
    error_reason: str,
    rejected_at: str,
) -> dict[str, Any]:
    return {
        "error_reason": error_reason,
        "rejected_at": rejected_at,
        "original": original,
    }


def dead_letter_key(original: Any) -> str | None:
    """`user_id` si existe y sirve como clave; `None` si no.

    Un motivo típico de rechazo es justamente que falte `user_id`, así que este
    es el único envío del sistema que puede ir sin clave de partición.
    """
    if not isinstance(original, Mapping):
        return None
    event = original.get("event")
    if not isinstance(event, Mapping):
        return None
    user_id = event.get("user_id")
    if isinstance(user_id, str) and user_id:
        return user_id
    return None
