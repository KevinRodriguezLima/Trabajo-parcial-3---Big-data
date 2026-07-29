from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from producers.benchmark import (  # noqa: E402
    CONFIGS,
    CSV_COLUMNS,
    BenchmarkConfig,
    BenchmarkResult,
    Latencies,
    percentile,
    resolve_file,
)
from producers.store import RUN_COLUMNS  # noqa: E402


class PercentileTests(unittest.TestCase):
    def test_single_sample(self) -> None:
        self.assertEqual(percentile([7.5], 99), 7.5)

    def test_known_quantiles(self) -> None:
        muestra = list(range(1, 101))
        self.assertAlmostEqual(percentile(muestra, 0), 1)
        self.assertAlmostEqual(percentile(muestra, 50), 50.5)
        self.assertAlmostEqual(percentile(muestra, 100), 100)

    def test_interpolates_between_samples(self) -> None:
        self.assertAlmostEqual(percentile([10.0, 20.0], 50), 15.0)

    def test_does_not_need_sorted_input(self) -> None:
        self.assertEqual(percentile([9.0, 1.0, 5.0], 50), 5.0)

    def test_tail_percentiles_are_ordered(self) -> None:
        muestra = [float(index) for index in range(1000)]
        p50, p95, p99 = (percentile(muestra, p) for p in (50, 95, 99))
        self.assertLess(p50, p95)
        self.assertLess(p95, p99)

    def test_empty_sample_is_an_error(self) -> None:
        with self.assertRaises(ValueError):
            percentile([], 50)

    def test_percentile_out_of_range(self) -> None:
        for p in (-1, 101):
            with self.subTest(p=p):
                with self.assertRaises(ValueError):
                    percentile([1.0, 2.0], p)


class LatenciesTests(unittest.TestCase):
    def test_empty_summary_is_all_zero(self) -> None:
        self.assertEqual(
            Latencies().summary(),
            {"p50": 0.0, "p95": 0.0, "p99": 0.0, "promedio": 0.0, "max": 0.0},
        )

    def test_summary_reports_the_three_percentiles(self) -> None:
        latencias = Latencies()
        for value in range(1, 101):
            latencias.add(float(value))
        resumen = latencias.summary()
        self.assertEqual(resumen["max"], 100.0)
        self.assertEqual(resumen["promedio"], 50.5)
        self.assertLess(resumen["p50"], resumen["p99"])

    def test_the_median_hides_the_tail_that_p99_shows(self) -> None:
        # Justificación de reportar percentiles y no solo el promedio: con un
        # 10 % de envíos lentos, la mediana ni se entera y el p99 sí.
        latencias = Latencies()
        for _ in range(90):
            latencias.add(1.0)
        for _ in range(10):
            latencias.add(500.0)
        resumen = latencias.summary()
        self.assertEqual(resumen["p50"], 1.0)
        self.assertEqual(resumen["p99"], 500.0)
        self.assertLess(resumen["promedio"], resumen["p99"])


class ConfigTests(unittest.TestCase):
    def test_the_two_compared_configurations(self) -> None:
        self.assertEqual(len(CONFIGS), 2)
        sin_espera, con_lote = CONFIGS
        self.assertEqual(sin_espera.linger_ms, 0)
        self.assertEqual(sin_espera.compression_type, "none")
        self.assertEqual(con_lote.linger_ms, 10)
        self.assertEqual(con_lote.compression_type, "lz4")

    def test_config_maps_to_kafka_names(self) -> None:
        config = BenchmarkConfig(label="x", linger_ms=10, compression_type="lz4")
        self.assertEqual(config.to_kafka(), {"linger.ms": 10, "compression.type": "lz4"})


class ResultTests(unittest.TestCase):
    def result(self, **overrides) -> BenchmarkResult:
        base = {
            "config": CONFIGS[0],
            "escenario": "BASE",
            "segundos": 10.0,
            "publicados": 1000,
            "enviados": 1000,
            "rechazados": 0,
            "fallidos": 0,
            "latencias": {"p50": 1.0, "p95": 2.0, "p99": 3.0, "promedio": 1.2, "max": 9.0},
        }
        return BenchmarkResult(**(base | overrides))

    def test_throughput_uses_confirmed_messages(self) -> None:
        # Lo encolado no mide nada si el broker no lo confirmó.
        self.assertEqual(self.result(enviados=500).eventos_por_segundo, 50.0)

    def test_zero_duration_does_not_divide_by_zero(self) -> None:
        self.assertEqual(self.result(segundos=0.0).eventos_por_segundo, 0.0)

    def test_row_matches_csv_columns(self) -> None:
        self.assertEqual(tuple(self.result().to_row()), CSV_COLUMNS)

    def test_notes_column_exists_for_benchmark_metrics(self) -> None:
        self.assertIn("notes", RUN_COLUMNS)


class ResolveFileTests(unittest.TestCase):
    def test_scenario_maps_to_the_simulator_output(self) -> None:
        self.assertEqual(
            resolve_file("CYBER_MONDAY", None),
            Path("simulator/output/cyber_monday/events.jsonl"),
        )

    def test_explicit_file_wins(self) -> None:
        elegido = Path("/tmp/otro.jsonl")
        self.assertEqual(resolve_file("BASE", elegido), elegido)


if __name__ == "__main__":
    unittest.main()
