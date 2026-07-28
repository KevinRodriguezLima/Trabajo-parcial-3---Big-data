from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .schema import Source


@dataclass(frozen=True, slots=True)
class ChannelConfig:
    """Lo único que distingue a un canal: su `source` y su perfil de latencia."""

    source: Source
    linger_ms: int
    batch_size: int
    compression_type: str = "lz4"

    @property
    def client_id(self) -> str:
        return f"producer-{self.source.value.lower()}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "linger_ms": self.linger_ms,
            "batch_size": self.batch_size,
            "compression_type": self.compression_type,
        }


# WEB y MOBILE concentran el 93 % del volumen: conviene esperar y mandar
# lotes grandes. POS es transaccional, así que espera poco. IOT y VEHICLE son
# telemetría de goteo: esperar no llena el lote, solo agrega latencia.
CHANNELS: dict[Source, ChannelConfig] = {
    Source.WEB: ChannelConfig(source=Source.WEB, linger_ms=20, batch_size=262144),
    Source.MOBILE: ChannelConfig(source=Source.MOBILE, linger_ms=20, batch_size=262144),
    Source.POS: ChannelConfig(source=Source.POS, linger_ms=5, batch_size=65536),
    Source.IOT: ChannelConfig(source=Source.IOT, linger_ms=0, batch_size=16384),
    Source.VEHICLE: ChannelConfig(source=Source.VEHICLE, linger_ms=0, batch_size=16384),
}


def channel_for(source: Source | str) -> ChannelConfig:
    try:
        return CHANNELS[Source(source)]
    except (KeyError, ValueError) as exc:
        raise ValueError(f"No hay canal para la fuente {source!r}") from exc
