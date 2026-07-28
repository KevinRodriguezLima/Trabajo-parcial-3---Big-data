from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Protocol

from .models import GeneratedMessage, SimulationStats
from .validation import validate_raw_event


class EventSink(Protocol):
    async def emit(self, message: GeneratedMessage) -> None: ...

    async def close(self) -> None: ...


class JsonlDirectorySink:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self.stats = SimulationStats()
        self._all_path = self.output_dir / "events.jsonl"
        self._all_path.write_text("", encoding="utf-8")
        for source in ("WEB", "MOBILE", "IOT", "VEHICLE", "POS"):
            (self.output_dir / f"events_{source.lower()}.jsonl").write_text("", encoding="utf-8")

    async def emit(self, message: GeneratedMessage) -> None:
        validate_raw_event(message.event)
        serialized = json.dumps(message.to_dict(), ensure_ascii=False, separators=(",", ":")) + "\n"
        source_path = self.output_dir / f"events_{message.source_hint.value.lower()}.jsonl"
        async with self._lock:
            with self._all_path.open("a", encoding="utf-8") as file:
                file.write(serialized)
            with source_path.open("a", encoding="utf-8") as file:
                file.write(serialized)
            self.stats.register(message)

    async def close(self) -> None:
        summary_path = self.output_dir / "summary.json"
        summary_path.write_text(
            json.dumps(self.stats.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


class ConsoleSink:
    def __init__(self, limit: int = 20) -> None:
        self.limit = max(limit, 0)
        self._printed = 0
        self._lock = asyncio.Lock()

    async def emit(self, message: GeneratedMessage) -> None:
        if self._printed >= self.limit:
            return
        async with self._lock:
            if self._printed < self.limit:
                print(json.dumps(message.to_dict(), ensure_ascii=False))
                self._printed += 1

    async def close(self) -> None:
        return None


class CompositeSink:
    def __init__(self, *sinks: EventSink) -> None:
        self.sinks = sinks

    async def emit(self, message: GeneratedMessage) -> None:
        for sink in self.sinks:
            await sink.emit(message)

    async def close(self) -> None:
        for sink in self.sinks:
            await sink.close()


class AsyncQueueSink:
    def __init__(self, maxsize: int = 10000) -> None:
        self.queue: asyncio.Queue[GeneratedMessage] = asyncio.Queue(maxsize=maxsize)

    async def emit(self, message: GeneratedMessage) -> None:
        validate_raw_event(message.event)
        await self.queue.put(message)

    async def close(self) -> None:
        return None
