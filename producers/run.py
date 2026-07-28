#!/usr/bin/env python3
"""Lee un JSONL del simulador y lo publica en Kafka a tasa controlada."""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from producers.base import BaseProducer, Counters  # noqa: E402
from producers.schema import Source  # noqa: E402


LOGGER = logging.getLogger("producers.run")
DEFAULT_FILE = Path("simulator/output/base/events.jsonl")
DEFAULT_BOOTSTRAP = "localhost:29092"


@dataclass(frozen=True, slots=True)
class ParsedLine:
    """Resultado de leer una línea: enrutable, o rechazo con motivo."""

    source: Source | None
    original: Any
    reason: str | None = None

    @property
    def routable(self) -> bool:
        return self.source is not None


def parse_line(line: str) -> ParsedLine:
    try:
        envelope = json.loads(line)
    except json.JSONDecodeError as exc:
        # El original va tal cual: sin JSON válido no hay sobre que conservar.
        return ParsedLine(source=None, original=line.rstrip("\n"), reason=f"JSON inválido: {exc}")

    if not isinstance(envelope, dict):
        return ParsedLine(source=None, original=envelope, reason="El mensaje no es un objeto JSON")

    try:
        source = Source(envelope.get("source_hint"))
    except ValueError:
        return ParsedLine(
            source=None,
            original=envelope,
            reason=f"source_hint fuera del contrato: {envelope.get('source_hint')!r}",
        )
    return ParsedLine(source=source, original=envelope)


def iter_lines(path: Path, limit: int | None = None) -> Iterator[str]:
    with path.open(encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            if limit is not None and index >= limit:
                return
            if line.strip():
                yield line


@dataclass(slots=True)
class Pacer:
    """Reparte los envíos a `rate` por segundo sin acumular deriva."""

    rate: float | None
    monotonic: Callable[[], float] = time.monotonic
    _started: float | None = None

    def delay_for(self, index: int, now: float) -> float:
        if not self.rate or self.rate <= 0:
            return 0.0
        if self._started is None:
            self._started = now
        objetivo = self._started + index / self.rate
        return max(0.0, objetivo - now)

    def wait(self, index: int) -> None:
        delay = self.delay_for(index, self.monotonic())
        if delay > 0:
            time.sleep(delay)


class Router:
    """Un producer por fuente; reparte según `source_hint`."""

    def __init__(self, *, bootstrap: str) -> None:
        self.producers: dict[Source, BaseProducer] = {
            source: BaseProducer(bootstrap=bootstrap, source=source) for source in Source
        }
        # Las líneas que no se pueden enrutar igual deben llegar al
        # dead-letter; cualquier producer sirve para emitirlas.
        self._fallback = self.producers[Source.WEB]

    def publish(self, parsed: ParsedLine) -> bool:
        if parsed.source is None:
            self._fallback.reject(parsed.original, parsed.reason or "No enrutable")
            return False
        return self.producers[parsed.source].publish(parsed.original)

    def counters(self) -> Counters:
        total = Counters()
        for producer in self.producers.values():
            total.merge(producer.counters)
        return total

    def close(self) -> int:
        return sum(producer.close() for producer in self.producers.values())

    def __enter__(self) -> Router:
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE, help="JSONL de entrada")
    parser.add_argument("--bootstrap", default=DEFAULT_BOOTSTRAP, help="Listener externo")
    parser.add_argument(
        "--rate",
        type=float,
        default=None,
        help="Eventos por segundo; sin el flag, tan rápido como se pueda",
    )
    parser.add_argument("--limit", type=int, default=None, help="Máximo de líneas a leer")
    parser.add_argument("--verbose", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
        stream=sys.stderr,
    )

    if not args.file.exists():
        raise SystemExit(f"No existe el archivo de entrada: {args.file}")

    run_id = uuid4().hex[:12]
    pacer = Pacer(rate=args.rate)
    started = time.time()
    started_monotonic = time.monotonic()
    leidas = 0

    LOGGER.info("corrida %s: %s (rate=%s, limit=%s)", run_id, args.file, args.rate, args.limit)

    with Router(bootstrap=args.bootstrap) as router:
        try:
            for index, line in enumerate(iter_lines(args.file, args.limit)):
                pacer.wait(index)
                router.publish(parse_line(line))
                leidas += 1
                if leidas % 5000 == 0:
                    LOGGER.info("%d líneas leídas", leidas)
        except KeyboardInterrupt:
            LOGGER.warning("interrumpido tras %d líneas; se vacía el buffer", leidas)

    elapsed = time.monotonic() - started_monotonic
    counters = router.counters()
    resumen = counters.to_dict() | {
        "run_id": run_id,
        "leidas": leidas,
        "segundos": round(elapsed, 2),
        "eventos_por_segundo": round(leidas / elapsed, 1) if elapsed > 0 else 0.0,
    }
    print(json.dumps(resumen, ensure_ascii=False, indent=2))

    _record_run(run_id, args, counters, started, elapsed)

    if counters.fallidos:
        raise SystemExit(f"{counters.fallidos} mensajes no se pudieron entregar")


def _record_run(
    run_id: str,
    args: argparse.Namespace,
    counters: Counters,
    started: float,
    elapsed: float,
) -> None:
    """Deja la corrida en la tabla `runs`. Si no hay base, solo avisa."""
    from datetime import datetime, timezone

    try:
        import psycopg

        from producers.store import INSERT_RUN, dsn_from_env
    except ImportError:
        LOGGER.warning("psycopg no está instalado: la corrida no se registró")
        return

    fila = (
        run_id,
        str(args.file),
        args.rate,
        datetime.fromtimestamp(started, timezone.utc),
        datetime.fromtimestamp(started + elapsed, timezone.utc),
        counters.publicados,
        counters.enviados,
        counters.rechazados,
        counters.fallidos,
    )
    try:
        with psycopg.connect(dsn_from_env(), connect_timeout=5) as conn:
            with conn.cursor() as cursor:
                cursor.execute(INSERT_RUN, fila)
        LOGGER.info("corrida %s registrada en la tabla runs", run_id)
    except Exception as exc:  # noqa: BLE001 - el registro no debe tumbar la corrida
        LOGGER.warning("no se registró la corrida %s: %s", run_id, exc)


if __name__ == "__main__":
    main()
