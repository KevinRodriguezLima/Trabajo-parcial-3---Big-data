from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional, Tuple
from .schemas import validate_raw_event, parse_iso_timestamp


class EventValidator:
    """
    Componente de validación, limpieza y enriquecimiento de eventos.
    Mantiene un buffer o caché de event_ids para deduplicación.
    """
    def __init__(self, max_dedup_cache_size: int = 10000):
        self.seen_event_ids = set()
        self.max_cache_size = max_dedup_cache_size

    def process(self, raw_message: str) -> Tuple[bool, Dict[str, Any], Optional[Dict[str, Any]]]:
        """
        Procesa una cadena JSON entrante.
        Retorna:
        - is_valid (bool)
        - valid_event / enriched_event (dict) si es válido
        - dead_letter_payload (dict) si no es válido o es duplicado
        """
        is_valid, data, error_reason = validate_raw_event(raw_message)

        if not is_valid:
            dead_letter = {
                "raw_message": raw_message,
                "error_reason": error_reason,
                "failed_at": datetime.now(timezone.utc).isoformat(),
                "event_id": data.get("event_id") if data else None
            }
            return False, {}, dead_letter

        event_id = data["event_id"]

        # Deduplicación
        if event_id in self.seen_event_ids:
            dead_letter = {
                "raw_message": raw_message,
                "error_reason": f"Duplicate event_id: {event_id}",
                "failed_at": datetime.now(timezone.utc).isoformat(),
                "event_id": event_id
            }
            return False, {}, dead_letter

        # Guardar event_id en memoria (LRU aproximado)
        if len(self.seen_event_ids) >= self.max_cache_size:
            self.seen_event_ids.pop()
        self.seen_event_ids.add(event_id)

        # Enriquecimiento con timestamps y latencia
        event_dt = parse_iso_timestamp(data["event_timestamp"])
        ingestion_dt = parse_iso_timestamp(data["ingestion_timestamp"])
        processing_dt = datetime.now(timezone.utc)

        latency_ms = 0
        if event_dt and ingestion_dt:
            latency_ms = max(0, int((ingestion_dt - event_dt).total_seconds() * 1000))

        enriched = dict(data)
        enriched["processing_timestamp"] = processing_dt.isoformat()
        enriched["latency_ms"] = latency_ms

        # Normalización / Trimming
        enriched["city"] = enriched["city"].strip()
        enriched["region"] = enriched["region"].strip()

        return True, enriched, None
