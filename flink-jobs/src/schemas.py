from datetime import datetime, timezone
import json
from typing import Any, Dict, Optional

REQUIRED_EVENT_FIELDS = [
    "event_id", "schema_version", "event_type", "event_timestamp",
    "ingestion_timestamp", "user_id", "session_id", "agent_profile",
    "source", "city", "region", "scenario", "payload"
]

VALID_EVENT_TYPES = {
    "LOGIN", "SEARCH", "PAGE_VIEW", "VIEW_PRODUCT", "ADD_TO_CART",
    "REMOVE_FROM_CART", "PURCHASE", "PAYMENT_FAILED", "GPS_UPDATE",
    "IOT_READING", "MOTION_DETECTED", "SOCIAL_POST"
}

VALID_SOURCES = {"WEB", "MOBILE", "IOT", "VEHICLE", "POS"}

def parse_iso_timestamp(ts_str: str) -> Optional[datetime]:
    """Convierte un string ISO 8601 a un objeto datetime UTC."""
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None

def timestamp_to_epoch_ms(ts_str: str) -> int:
    """Convierte timestamp ISO 8601 a milisegundos desde epoch."""
    dt = parse_iso_timestamp(ts_str)
    if dt:
        return int(dt.timestamp() * 1000)
    return 0

def validate_raw_event(raw_json: str) -> tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Valida un evento raw JSON contra el contrato v1.0.
    Retorna (is_valid, parsed_dict, error_reason).
    """
    try:
        data = json.loads(raw_json)
    except Exception as e:
        return False, None, f"JSON malformado: {str(e)}"

    if not isinstance(data, dict):
        return False, None, "El evento debe ser un objeto JSON"

    for req in REQUIRED_EVENT_FIELDS:
        if req not in data or data[req] is None:
            return False, data, f"Campo requerido ausente o nulo: {req}"

    if data.get("schema_version") != "1.0":
        return False, data, f"Versión de esquema no soportada: {data.get('schema_version')}"

    if data.get("event_type") not in VALID_EVENT_TYPES:
        return False, data, f"event_type inválido: {data.get('event_type')}"

    if data.get("source") not in VALID_SOURCES:
        return False, data, f"source inválido: {data.get('source')}"

    event_dt = parse_iso_timestamp(data.get("event_timestamp", ""))
    if not event_dt:
        return False, data, f"event_timestamp no es un ISO 8601 válido: {data.get('event_timestamp')}"

    return True, data, None
