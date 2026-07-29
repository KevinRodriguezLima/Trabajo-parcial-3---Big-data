from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .schema import EVENT_SCHEMA_PATH, SOURCE_FIELDS, EventType, Source


class ValidationError(ValueError):
    """Motivo de rechazo. El texto viaja tal cual al dead-letter."""


@dataclass(frozen=True, slots=True)
class EnvelopeRules:
    required: frozenset[str]
    enums: dict[str, frozenset[str]]
    consts: dict[str, Any]
    non_empty: frozenset[str]
    timestamps: frozenset[str]


def load_payload_requirements(
    path: Path = EVENT_SCHEMA_PATH,
) -> dict[EventType, frozenset[str]]:
    """Campos obligatorios de cada payload, leídos de las ramas del contrato.

    Cada rama `allOf` liga un `event_type` con un `$ref` a `$defs`, así que la
    tabla sale del contrato en lugar de duplicarse aquí.
    """
    schema = json.loads(path.read_text(encoding="utf-8"))
    defs = schema["$defs"]
    requirements: dict[EventType, frozenset[str]] = {}
    for branch in schema.get("allOf", ()):
        event_type = branch["if"]["properties"]["event_type"]["const"]
        reference = branch["then"]["properties"]["payload"]["$ref"]
        definition = defs[reference.rsplit("/", 1)[-1]]
        requirements[EventType(event_type)] = frozenset(definition["required"])
    return requirements


def load_item_requirements(path: Path = EVENT_SCHEMA_PATH) -> frozenset[str]:
    schema = json.loads(path.read_text(encoding="utf-8"))
    return frozenset(schema["$defs"]["purchaseItem"]["required"])


def load_envelope_rules(path: Path = EVENT_SCHEMA_PATH) -> EnvelopeRules:
    schema = json.loads(path.read_text(encoding="utf-8"))
    properties = schema["properties"]

    enums: dict[str, frozenset[str]] = {}
    consts: dict[str, Any] = {}
    non_empty: set[str] = set()
    timestamps: set[str] = set()

    for name, definition in properties.items():
        if "enum" in definition:
            enums[name] = frozenset(definition["enum"])
        if "const" in definition:
            consts[name] = definition["const"]
        if definition.get("type") == "string":
            if definition.get("format") == "date-time":
                timestamps.add(name)
            elif definition.get("minLength", 0) >= 1:
                non_empty.add(name)

    return EnvelopeRules(
        required=frozenset(schema["required"]),
        enums=enums,
        consts=consts,
        non_empty=frozenset(non_empty),
        timestamps=frozenset(timestamps),
    )


PAYLOAD_REQUIREMENTS: dict[EventType, frozenset[str]] = load_payload_requirements()
ITEM_REQUIREMENTS: frozenset[str] = load_item_requirements()
ENVELOPE_RULES: EnvelopeRules = load_envelope_rules()


def validate_input(envelope: Any) -> None:
    """Paso 1: lo que entrega A. `event_id` y `source` todavía no existen."""
    if not isinstance(envelope, Mapping):
        raise ValidationError("El mensaje no es un objeto JSON")

    event = envelope.get("event")
    if not isinstance(event, Mapping):
        raise ValidationError("El sobre no trae un objeto 'event'")

    # Primero el event_type: sin él no se sabe qué payload exigir, y el
    # validador del contrato devolvería doce fallos simultáneos ilegibles.
    raw_type = event.get("event_type")
    if raw_type is None:
        raise ValidationError("Falta event_type")
    try:
        event_type = EventType(raw_type)
    except ValueError:
        raise ValidationError(f"event_type fuera del contrato: {raw_type!r}") from None

    missing = [field for field in SOURCE_FIELDS if field not in event]
    if missing:
        raise ValidationError(f"Faltan campos de A: {sorted(missing)}")

    for field in ("event_timestamp", "user_id", "session_id", "city", "region"):
        value = event[field]
        if not isinstance(value, str) or not value:
            raise ValidationError(f"{field} debe ser una cadena no vacía")

    source_hint = envelope.get("source_hint")
    try:
        Source(source_hint)
    except ValueError:
        raise ValidationError(f"source_hint fuera del contrato: {source_hint!r}") from None

    payload = event["payload"]
    if not isinstance(payload, Mapping):
        raise ValidationError("payload debe ser un objeto")

    faltantes = PAYLOAD_REQUIREMENTS[event_type] - set(payload)
    if faltantes:
        raise ValidationError(
            f"Payload de {event_type.value} incompleto: faltan {sorted(faltantes)}"
        )

    if event_type is EventType.PURCHASE:
        _validate_purchase_items(payload["items"])


def _validate_purchase_items(items: Any) -> None:
    if not isinstance(items, list) or not items:
        raise ValidationError("PURCHASE.items debe ser un arreglo no vacío")
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise ValidationError(f"PURCHASE.items[{index}] no es un objeto")
        faltantes = ITEM_REQUIREMENTS - set(item)
        if faltantes:
            raise ValidationError(
                f"PURCHASE.items[{index}] incompleto: faltan {sorted(faltantes)}"
            )


def validate_event(event: Any) -> None:
    """Paso 3: el evento ya enriquecido, contra las reglas de event.schema.json."""
    if not isinstance(event, Mapping):
        raise ValidationError("El evento publicado no es un objeto")

    claves = set(event)
    faltantes = ENVELOPE_RULES.required - claves
    if faltantes:
        raise ValidationError(f"El evento no tiene {sorted(faltantes)}")
    # additionalProperties: false. Aquí es donde se cacharía un source_hint
    # que se haya colado en el evento publicado.
    sobrantes = claves - ENVELOPE_RULES.required
    if sobrantes:
        raise ValidationError(f"El evento trae campos fuera del contrato: {sorted(sobrantes)}")

    for field, allowed in ENVELOPE_RULES.enums.items():
        if event[field] not in allowed:
            raise ValidationError(f"{field} fuera del contrato: {event[field]!r}")

    for field, expected in ENVELOPE_RULES.consts.items():
        if event[field] != expected:
            raise ValidationError(f"{field} debe ser {expected!r}, no {event[field]!r}")

    for field in ENVELOPE_RULES.non_empty:
        value = event[field]
        if not isinstance(value, str) or not value:
            raise ValidationError(f"{field} debe ser una cadena no vacía")

    for field in ENVELOPE_RULES.timestamps:
        _validate_timestamp(field, event[field])

    if not isinstance(event["payload"], Mapping):
        raise ValidationError("payload debe ser un objeto")


def _validate_timestamp(field: str, value: Any) -> None:
    if not isinstance(value, str):
        raise ValidationError(f"{field} debe ser una cadena ISO-8601")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"{field} no es ISO-8601: {value!r}") from None
    if parsed.tzinfo is None:
        raise ValidationError(f"{field} debe traer zona horaria: {value!r}")
