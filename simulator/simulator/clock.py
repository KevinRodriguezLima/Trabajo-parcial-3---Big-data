from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass(slots=True)
class VirtualClock:
    start_virtual: datetime
    speed_factor: float
    _start_real: float = field(default_factory=time.monotonic, init=False)

    def __post_init__(self) -> None:
        if self.start_virtual.tzinfo is None:
            raise ValueError("start_virtual debe incluir zona horaria")
        if self.speed_factor <= 0:
            raise ValueError("speed_factor debe ser mayor que cero")

    def now(self) -> datetime:
        elapsed_real = time.monotonic() - self._start_real
        return self.start_virtual + timedelta(seconds=elapsed_real * self.speed_factor)

    def iso_now(self) -> str:
        return self.now().isoformat(timespec="milliseconds")
