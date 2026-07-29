from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from producers.base import Counters  # noqa: E402
from producers.channels import CHANNELS, channel_for  # noqa: E402
from producers.schema import Source  # noqa: E402


class ChannelTests(unittest.TestCase):
    def test_there_is_one_channel_per_source(self) -> None:
        self.assertEqual(set(CHANNELS), set(Source))

    def test_each_channel_declares_its_own_source(self) -> None:
        for source, channel in CHANNELS.items():
            with self.subTest(source=source.value):
                self.assertIs(channel.source, source)

    def test_client_ids_are_unique(self) -> None:
        ids = {channel.client_id for channel in CHANNELS.values()}
        self.assertEqual(len(ids), len(Source))
        self.assertEqual(CHANNELS[Source.WEB].client_id, "producer-web")

    def test_high_volume_channels_wait_more_than_telemetry(self) -> None:
        self.assertGreater(CHANNELS[Source.WEB].linger_ms, CHANNELS[Source.IOT].linger_ms)
        self.assertGreater(CHANNELS[Source.MOBILE].batch_size, CHANNELS[Source.VEHICLE].batch_size)

    def test_channel_for_accepts_enum_and_string(self) -> None:
        self.assertIs(channel_for("POS"), CHANNELS[Source.POS])
        self.assertIs(channel_for(Source.POS), CHANNELS[Source.POS])

    def test_unknown_source_has_no_channel(self) -> None:
        with self.assertRaises(ValueError):
            channel_for("SMARTWATCH")


class CountersTests(unittest.TestCase):
    def test_starts_at_zero(self) -> None:
        self.assertEqual(
            Counters().to_dict(),
            {"publicados": 0, "enviados": 0, "rechazados": 0, "fallidos": 0},
        )

    def test_merge_adds_up(self) -> None:
        total = Counters(publicados=2, enviados=2)
        total.merge(Counters(publicados=3, enviados=1, rechazados=1, fallidos=1))
        self.assertEqual(
            total.to_dict(),
            {"publicados": 5, "enviados": 3, "rechazados": 1, "fallidos": 1},
        )


if __name__ == "__main__":
    unittest.main()
