from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from producers.partitioning import murmur2, partition_for_key  # noqa: E402


class Murmur2Tests(unittest.TestCase):
    def test_stays_in_unsigned_32_bits(self) -> None:
        for key in ("", "a", "USR000030", "USR000030-largo" * 7):
            with self.subTest(key=key):
                self.assertTrue(0 <= murmur2(key.encode("utf-8")) <= 0xFFFFFFFF)

    def test_is_deterministic(self) -> None:
        self.assertEqual(murmur2(b"USR000030"), murmur2(b"USR000030"))

    def test_distinguishes_similar_keys(self) -> None:
        self.assertNotEqual(murmur2(b"USR000030"), murmur2(b"USR000031"))

    def test_covers_the_four_tail_lengths(self) -> None:
        # Las cuatro ramas del switch final (length % 4) se ejercitan aquí.
        values = {murmur2(b"a" * length) for length in (4, 5, 6, 7)}
        self.assertEqual(len(values), 4)


class PartitionForKeyTests(unittest.TestCase):
    def test_is_inside_range(self) -> None:
        for index in range(200):
            with self.subTest(index=index):
                self.assertIn(partition_for_key(f"USR{index:06d}", 4), range(4))

    def test_same_key_always_lands_in_same_partition(self) -> None:
        partitions = {partition_for_key("USR000030", 4) for _ in range(10)}
        self.assertEqual(len(partitions), 1)

    def test_uses_every_partition(self) -> None:
        used = {partition_for_key(f"USR{index:06d}", 4) for index in range(200)}
        self.assertEqual(used, {0, 1, 2, 3})

    def test_single_partition_topic_always_zero(self) -> None:
        self.assertEqual(partition_for_key("USR000030", 1), 0)

    def test_rejects_invalid_partition_count(self) -> None:
        with self.assertRaises(ValueError):
            partition_for_key("USR000030", 0)


if __name__ == "__main__":
    unittest.main()
