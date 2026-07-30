from datetime import datetime, timezone, timedelta
import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from confluent_kafka import Consumer, KafkaException
    HAS_KAFKA = True
except ImportError:
    Consumer = None
    KafkaException = Exception
    HAS_KAFKA = False

from src.config import CONFIG
from src.validation import EventValidator
from src.metrics.throughput import calculate_throughput
from src.metrics.active_users import calculate_active_users
from src.metrics.events_by_type import calculate_events_by_type
from src.metrics.top_products import calculate_top_viewed_products, calculate_top_purchased_products
from src.metrics.purchases_by_region import calculate_purchases_by_region
from src.metrics.conversion import calculate_conversion
from src.metrics.trends import calculate_trends
from src.audiences.classifier import AudienceClassifierRegistry
from src.alerts.anomaly_detector import AnomalyDetector
from src.sinks import OutputPublisher

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
LOGGER = logging.getLogger("flink.main")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat()


class FlinkJobPipeline:
    """
    Orquestador principal del pipeline de procesamiento en tiempo real.

    El proyecto conserva este nombre porque el job se ejecuta desde el cluster
    Flink local, pero la unidad testeable es una microventana de mensajes Kafka.
    """
    def __init__(self):
        self.validator = EventValidator()
        self.audience_registry = AudienceClassifierRegistry()
        self.anomaly_detector = AnomalyDetector()
        self.publisher = OutputPublisher()
        self.user_events_history: Dict[str, List[Dict[str, Any]]] = {}

    def process_batch(self, raw_messages: List[str], window_start: str, window_end: str):
        valid_events: List[Dict[str, Any]] = []
        dead_letter_events: List[Dict[str, Any]] = []

        for raw in raw_messages:
            is_valid, enriched, dl = self.validator.process(raw)
            if is_valid:
                valid_events.append(enriched)
                uid = enriched["user_id"]
                if uid not in self.user_events_history:
                    self.user_events_history[uid] = []
                self.user_events_history[uid].append(enriched)
                self.user_events_history[uid] = self.user_events_history[uid][-500:]
            elif dl:
                dead_letter_events.append(dl)

        LOGGER.info(
            "Ventana %s -> %s: %d eventos validos, %d a dead-letter",
            window_start, window_end, len(valid_events), len(dead_letter_events)
        )

        if not valid_events:
            return

        win_sec = CONFIG.kafka_batch_window_sec

        tp_res = calculate_throughput(valid_events, win_sec)
        self.publisher.publish_metric("throughput", window_start, window_end, tp_res)

        au_res = calculate_active_users(valid_events)
        self.publisher.publish_metric("active_users", window_start, window_end, au_res)

        ebt_res = calculate_events_by_type(valid_events)
        self.publisher.publish_metric("events_by_type", window_start, window_end, ebt_res)

        tpv_res = calculate_top_viewed_products(valid_events)
        self.publisher.publish_metric("top_products_viewed", window_start, window_end, tpv_res)

        tpp_res = calculate_top_purchased_products(valid_events)
        self.publisher.publish_metric("top_products_purchased", window_start, window_end, tpp_res)

        pbr_res = calculate_purchases_by_region(valid_events)
        self.publisher.publish_metric("purchases_by_region", window_start, window_end, pbr_res)

        conv_res = calculate_conversion(valid_events)
        self.publisher.publish_metric("conversion", window_start, window_end, conv_res)

        tr_res = calculate_trends(valid_events)
        self.publisher.publish_metric("trends", window_start, window_end, tr_res)

        active_users_in_batch = {e["user_id"] for e in valid_events}
        for uid in active_users_in_batch:
            user_history = self.user_events_history.get(uid, [])
            audience_results = self.audience_registry.evaluate_user(uid, user_history)
            for aud in audience_results:
                self.publisher.publish_audience(aud.to_dict())

        alerts = self.anomaly_detector.detect(valid_events, window_start, window_end)
        for alert in alerts:
            self.publisher.publish_alert(alert)

    def close(self):
        self.publisher.close()


class KafkaMicroBatchRunner:
    """Consume Kafka continuamente y entrega microventanas al pipeline."""

    def __init__(
        self,
        pipeline: FlinkJobPipeline,
        *,
        bootstrap: str,
        topics: List[str],
        group_id: str,
        window_seconds: int,
        max_batch_size: int,
        poll_timeout: float,
    ):
        if not HAS_KAFKA or Consumer is None:
            raise RuntimeError("confluent_kafka no esta instalado. Ejecuta: pip install -r flink-jobs/requirements.txt")
        self.pipeline = pipeline
        self.topics = topics
        self.window_seconds = window_seconds
        self.max_batch_size = max_batch_size
        self.poll_timeout = poll_timeout
        self.consumer = Consumer({
            "bootstrap.servers": bootstrap,
            "group.id": group_id,
            "auto.offset.reset": CONFIG.kafka_auto_offset_reset,
            "enable.auto.commit": False,
            "client.id": "flink-microbatch-consumer",
        })

    def run_forever(self):
        self.consumer.subscribe(self.topics)
        LOGGER.info("Consumiendo topics=%s bootstrap=%s", ",".join(self.topics), CONFIG.kafka_bootstrap_internal)
        window_start = utc_now()
        batch: List[str] = []
        try:
            while True:
                msg = self.consumer.poll(self.poll_timeout)
                if msg is not None:
                    if msg.error():
                        raise KafkaException(msg.error())
                    batch.append(msg.value().decode("utf-8"))

                elapsed = (utc_now() - window_start).total_seconds()
                should_flush = elapsed >= self.window_seconds or len(batch) >= self.max_batch_size
                if should_flush:
                    window_end = utc_now()
                    if batch:
                        self.pipeline.process_batch(batch, iso(window_start), iso(window_end))
                        self.consumer.commit(asynchronous=False)
                    batch = []
                    window_start = utc_now()
        except KeyboardInterrupt:
            LOGGER.info("Interrumpido por usuario; cerrando consumidor")
        finally:
            if batch:
                window_end = utc_now()
                self.pipeline.process_batch(batch, iso(window_start), iso(window_end))
                self.consumer.commit(asynchronous=False)
            self.consumer.close()
            self.pipeline.close()


def read_jsonl(path: str) -> List[str]:
    with open(path, encoding="utf-8") as handle:
        return [line.rstrip("\n") for line in handle if line.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Procesador C: Kafka -> metricas/audiencias/alertas -> Postgres/Kafka")
    parser.add_argument("--bootstrap", default=CONFIG.kafka_bootstrap_internal)
    parser.add_argument("--topics", default=CONFIG.kafka_input_topics)
    parser.add_argument("--group-id", default=CONFIG.group_id)
    parser.add_argument("--window-sec", type=int, default=CONFIG.kafka_batch_window_sec)
    parser.add_argument("--max-batch-size", type=int, default=CONFIG.kafka_max_batch_size)
    parser.add_argument("--poll-timeout", type=float, default=CONFIG.kafka_poll_timeout_sec)
    parser.add_argument("--once-file", help="Procesa un JSONL enriquecido una sola vez, util para pruebas")
    return parser


def main(argv: Optional[List[str]] = None):
    args = build_parser().parse_args(argv)
    pipeline = FlinkJobPipeline()

    if args.once_file:
        start = utc_now()
        messages = read_jsonl(args.once_file)
        pipeline.process_batch(messages, iso(start), iso(start + timedelta(seconds=args.window_sec)))
        pipeline.close()
        return

    topics = [topic.strip() for topic in args.topics.split(",") if topic.strip()]
    runner = KafkaMicroBatchRunner(
        pipeline,
        bootstrap=args.bootstrap,
        topics=topics,
        group_id=args.group_id,
        window_seconds=args.window_sec,
        max_batch_size=args.max_batch_size,
        poll_timeout=args.poll_timeout,
    )
    runner.run_forever()


if __name__ == "__main__":
    main(sys.argv[1:])
