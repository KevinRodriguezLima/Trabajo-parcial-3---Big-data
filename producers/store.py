from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


EVENT_COLUMNS: tuple[str, ...] = (
    "event_id",
    "schema_version",
    "event_type",
    "event_timestamp",
    "ingestion_timestamp",
    "user_id",
    "session_id",
    "agent_profile",
    "source",
    "city",
    "region",
    "scenario",
    "payload",
    "kafka_topic",
    "kafka_partition",
    "kafka_offset",
)

# payload viaja como texto y Postgres lo convierte: así el armado de filas no
# depende del driver y se puede probar sin psycopg instalado.
INSERT_EVENTS = (
    "INSERT INTO events ("
    + ", ".join(EVENT_COLUMNS)
    + ") VALUES ("
    + ", ".join("%s::jsonb" if column == "payload" else "%s" for column in EVENT_COLUMNS)
    + ") ON CONFLICT (event_id) DO NOTHING"
)

INSERT_RUN = (
    "INSERT INTO runs ("
    "run_id, source_file, rate, started_at, finished_at, "
    "publicados, enviados, rechazados, fallidos"
    ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
    "ON CONFLICT (run_id) DO NOTHING"
)

DEFAULT_DSN = "postgresql://audiencias:audiencias@localhost:5432/audiencias"


def dsn_from_env(environ: Mapping[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    return env.get("POSTGRES_DSN", DEFAULT_DSN)


def row_from_event(
    event: Mapping[str, Any],
    *,
    topic: str,
    partition: int,
    offset: int,
) -> tuple[Any, ...]:
    """Convierte el evento de 13 campos en la fila de `events`."""
    values: list[Any] = []
    for column in EVENT_COLUMNS:
        if column == "payload":
            values.append(json.dumps(event["payload"], ensure_ascii=False))
        elif column == "kafka_topic":
            values.append(topic)
        elif column == "kafka_partition":
            values.append(partition)
        elif column == "kafka_offset":
            values.append(offset)
        else:
            values.append(event[column])
    return tuple(values)


@dataclass(slots=True)
class Batch:
    """Acumula filas hasta llenar el lote o agotar la ventana de tiempo."""

    max_rows: int = 500
    max_seconds: float = 2.0
    rows: list[tuple[Any, ...]] = field(default_factory=list)
    opened_at: float | None = None

    def add(self, row: tuple[Any, ...], now: float) -> None:
        if not self.rows:
            self.opened_at = now
        self.rows.append(row)

    def should_flush(self, now: float) -> bool:
        if not self.rows:
            return False
        if len(self.rows) >= self.max_rows:
            return True
        return self.opened_at is not None and now - self.opened_at >= self.max_seconds

    def drain(self) -> list[tuple[Any, ...]]:
        rows = self.rows
        self.rows = []
        self.opened_at = None
        return rows

    def __len__(self) -> int:
        return len(self.rows)
