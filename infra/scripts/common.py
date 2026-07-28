from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / "infra" / ".env"
FALLBACK_BOOTSTRAP = "localhost:29092"


def ensure_root_on_path() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))


def load_env_file(path: Path = ENV_PATH) -> None:
    """Carga infra/.env sin pisar lo que ya venga del entorno real."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def default_bootstrap() -> str:
    load_env_file()
    return os.environ.get("KAFKA_BOOTSTRAP_EXTERNAL", FALLBACK_BOOTSTRAP)


def build_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--bootstrap-servers",
        default=default_bootstrap(),
        help="Listener externo del broker (por defecto, el de infra/.env)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Segundos de espera en las llamadas al broker",
    )
    return parser


def client_logger(verbose: bool = False) -> logging.Logger:
    """Desvía los logs de librdkafka a Python.

    Sin `--verbose` tapan el error real: reintenta la conexión cada 60 ms y
    escribe una línea por intento directo a stderr.
    """
    logger = logging.getLogger("rdkafka")
    logger.setLevel(logging.DEBUG if verbose else logging.CRITICAL)
    return logger


def configure_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(message)s",
        stream=sys.stderr,
    )
