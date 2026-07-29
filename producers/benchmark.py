#!/usr/bin/env python3
"""Mide el throughput máximo y la latencia de publicación, sin límite de tasa."""
from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import socket
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from producers.run import Router, parse_line  # noqa: E402


LOGGER = logging.getLogger("producers.benchmark")
DEFAULT_BOOTSTRAP = "localhost:29092"
DEFAULT_CSV = Path("docs/reports/parte-b-benchmark.csv")
KAFKA_UI_PORT = 8080


@dataclass(frozen=True, slots=True)
class BenchmarkConfig:
    label: str
    linger_ms: int
    compression_type: str

    def to_kafka(self) -> dict[str, Any]:
        return {"linger.ms": self.linger_ms, "compression.type": self.compression_type}


# Las dos configuraciones que se comparan: latencia mínima contra
# aprovechamiento del lote.
CONFIGS: tuple[BenchmarkConfig, ...] = (
    BenchmarkConfig(label="linger0-sin-compresion", linger_ms=0, compression_type="none"),
    BenchmarkConfig(label="linger10-lz4", linger_ms=10, compression_type="lz4"),
)

CSV_COLUMNS: tuple[str, ...] = (
    "configuracion",
    "linger_ms",
    "compresion",
    "escenario",
    "segundos",
    "publicados",
    "enviados",
    "rechazados",
    "fallidos",
    "eventos_por_segundo",
    "latencia_p50_ms",
    "latencia_p95_ms",
    "latencia_p99_ms",
    "latencia_promedio_ms",
    "latencia_max_ms",
)


def percentile(values: Sequence[float], p: float) -> float:
    """Percentil con interpolación lineal sobre la muestra ordenada."""
    if not values:
        raise ValueError("No hay muestras para calcular el percentil")
    if not 0.0 <= p <= 100.0:
        raise ValueError(f"El percentil debe estar entre 0 y 100, no {p}")
    ordenados = sorted(values)
    if len(ordenados) == 1:
        return ordenados[0]
    posicion = (p / 100.0) * (len(ordenados) - 1)
    inferior = math.floor(posicion)
    superior = math.ceil(posicion)
    if inferior == superior:
        return ordenados[inferior]
    peso = posicion - inferior
    return ordenados[inferior] + (ordenados[superior] - ordenados[inferior]) * peso


@dataclass(slots=True)
class Latencies:
    values: list[float] = field(default_factory=list)

    def add(self, milliseconds: float) -> None:
        self.values.append(milliseconds)

    def summary(self) -> dict[str, float]:
        if not self.values:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "promedio": 0.0, "max": 0.0}
        return {
            "p50": round(percentile(self.values, 50), 2),
            "p95": round(percentile(self.values, 95), 2),
            "p99": round(percentile(self.values, 99), 2),
            "promedio": round(sum(self.values) / len(self.values), 2),
            "max": round(max(self.values), 2),
        }


@dataclass(slots=True)
class BenchmarkResult:
    config: BenchmarkConfig
    escenario: str
    segundos: float
    publicados: int
    enviados: int
    rechazados: int
    fallidos: int
    latencias: dict[str, float]

    @property
    def eventos_por_segundo(self) -> float:
        return round(self.enviados / self.segundos, 1) if self.segundos > 0 else 0.0

    def to_row(self) -> dict[str, Any]:
        return {
            "configuracion": self.config.label,
            "linger_ms": self.config.linger_ms,
            "compresion": self.config.compression_type,
            "escenario": self.escenario,
            "segundos": round(self.segundos, 2),
            "publicados": self.publicados,
            "enviados": self.enviados,
            "rechazados": self.rechazados,
            "fallidos": self.fallidos,
            "eventos_por_segundo": self.eventos_por_segundo,
            "latencia_p50_ms": self.latencias["p50"],
            "latencia_p95_ms": self.latencias["p95"],
            "latencia_p99_ms": self.latencias["p99"],
            "latencia_promedio_ms": self.latencias["promedio"],
            "latencia_max_ms": self.latencias["max"],
        }


def resolve_file(scenario: str, explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    return Path("simulator/output") / scenario.lower() / "events.jsonl"


def load_lines(path: Path) -> list[str]:
    """Carga el archivo en memoria: el disco no debe entrar en la medición."""
    with path.open(encoding="utf-8") as handle:
        return [line for line in handle if line.strip()]


def tools_are_running(port: int = KAFKA_UI_PORT) -> bool:
    try:
        with socket.create_connection(("localhost", port), timeout=0.3):
            return True
    except OSError:
        return False


def run_config(
    config: BenchmarkConfig,
    *,
    lines: list[str],
    duration: float,
    bootstrap: str,
    escenario: str,
) -> BenchmarkResult:
    latencias = Latencies()
    inicio = time.monotonic()
    limite = inicio + duration
    indice = 0

    with Router(
        bootstrap=bootstrap,
        extra_config=config.to_kafka(),
        latency_observer=latencias.add,
    ) as router:
        while time.monotonic() < limite:
            # El archivo se recicla si se acaba: cada publicación genera su
            # propio event_id, así que no se repiten claves.
            router.publish(parse_line(lines[indice % len(lines)]))
            indice += 1
        publicacion = time.monotonic() - inicio

    total = time.monotonic() - inicio
    counters = router.counters()
    LOGGER.info(
        "%s: %d publicados en %.2f s (%.2f s con el flush final)",
        config.label,
        counters.publicados,
        publicacion,
        total,
    )
    return BenchmarkResult(
        config=config,
        escenario=escenario,
        segundos=total,
        publicados=counters.publicados,
        enviados=counters.enviados,
        rechazados=counters.rechazados,
        fallidos=counters.fallidos,
        latencias=latencias.summary(),
    )


def render(results: Sequence[BenchmarkResult]) -> str:
    encabezado = (
        f"{'CONFIGURACIÓN':<24}{'ENVIADOS':>9}{'EV/S':>9}"
        f"{'p50 ms':>9}{'p95 ms':>9}{'p99 ms':>9}{'MAX ms':>9}{'FALLIDOS':>9}"
    )
    lineas = [encabezado, "-" * len(encabezado)]
    for result in results:
        lineas.append(
            f"{result.config.label:<24}"
            f"{result.enviados:>9}"
            f"{result.eventos_por_segundo:>9}"
            f"{result.latencias['p50']:>9}"
            f"{result.latencias['p95']:>9}"
            f"{result.latencias['p99']:>9}"
            f"{result.latencias['max']:>9}"
            f"{result.fallidos:>9}"
        )
    return "\n".join(lineas)


def write_csv(path: Path, results: Sequence[BenchmarkResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for result in results:
            writer.writerow(result.to_row())


def record_runs(results: Sequence[BenchmarkResult], source_file: Path) -> None:
    """Deja cada corrida en `runs`; las métricas van en `notes`."""
    from datetime import datetime, timezone

    try:
        import psycopg

        from producers.store import INSERT_RUN, dsn_from_env
    except ImportError:
        LOGGER.warning("psycopg no está instalado: las corridas no se registraron")
        return

    ahora = datetime.now(timezone.utc)
    filas = [
        (
            f"bench_{uuid4().hex[:8]}",
            str(source_file),
            None,  # sin límite de tasa: la corrida mide el máximo
            ahora,
            ahora,
            result.publicados,
            result.enviados,
            result.rechazados,
            result.fallidos,
            json.dumps(result.to_row(), ensure_ascii=False),
        )
        for result in results
    ]
    try:
        with psycopg.connect(dsn_from_env(), connect_timeout=5) as conn:
            with conn.cursor() as cursor:
                cursor.executemany(INSERT_RUN, filas)
        LOGGER.info("%d corridas registradas en la tabla runs", len(filas))
    except Exception as exc:  # noqa: BLE001 - el registro no debe tumbar el benchmark
        LOGGER.warning("no se registraron las corridas: %s", exc)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=None, help="JSONL de entrada")
    parser.add_argument("--scenario", default="BASE", help="Escenario del simulador")
    parser.add_argument(
        "--duration",
        type=float,
        default=20.0,
        help="Segundos de publicación por configuración",
    )
    parser.add_argument("--bootstrap", default=DEFAULT_BOOTSTRAP)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument(
        "--ignore-tools",
        action="store_true",
        help="Mide aunque la consola web esté levantada",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
        stream=sys.stderr,
    )

    if tools_are_running() and not args.ignore_tools:
        raise SystemExit(
            "La consola web responde en el puerto 8080. Consume CPU y contamina la "
            "medición: baja el profile tools (docker compose --profile tools down) "
            "o usa --ignore-tools."
        )

    path = resolve_file(args.scenario, args.file)
    if not path.exists():
        raise SystemExit(f"No existe el archivo de entrada: {path}")

    lines = load_lines(path)
    if not lines:
        raise SystemExit(f"El archivo está vacío: {path}")
    LOGGER.info("%d líneas en memoria desde %s", len(lines), path)

    results = [
        run_config(
            config,
            lines=lines,
            duration=args.duration,
            bootstrap=args.bootstrap,
            escenario=args.scenario,
        )
        for config in CONFIGS
    ]

    print(render(results))
    write_csv(args.csv, results)
    LOGGER.info("CSV escrito en %s", args.csv)
    record_runs(results, path)

    fallidos = sum(result.fallidos for result in results)
    if fallidos:
        raise SystemExit(f"{fallidos} mensajes no se pudieron entregar")


if __name__ == "__main__":
    main()
