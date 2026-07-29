from datetime import datetime, timezone, timedelta
import json
import logging
import sys
import time
from typing import Any, Dict, List

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


class FlinkJobPipeline:
    """
    Orquestador principal del pipeline de Flink para procesamiento en tiempo real.
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

        # 1. Validación, limpieza y deduplicación
        for raw in raw_messages:
            is_valid, enriched, dl = self.validator.process(raw)
            if is_valid:
                valid_events.append(enriched)
                uid = enriched["user_id"]
                if uid not in self.user_events_history:
                    self.user_events_history[uid] = []
                self.user_events_history[uid].append(enriched)
            elif dl:
                dead_letter_events.append(dl)

        LOGGER.info(
            "Ventana %s -> %s: %d eventos válidos, %d a dead-letter",
            window_start, window_end, len(valid_events), len(dead_letter_events)
        )

        if not valid_events:
            return

        # 2. Métricas
        win_sec = CONFIG.windows.throughput_window_sec

        # 2.1 Throughput
        tp_res = calculate_throughput(valid_events, win_sec)
        self.publisher.publish_metric("throughput", window_start, window_end, tp_res)

        # 2.2 Active Users
        au_res = calculate_active_users(valid_events)
        self.publisher.publish_metric("active_users", window_start, window_end, au_res)

        # 2.3 Events By Type
        ebt_res = calculate_events_by_type(valid_events)
        self.publisher.publish_metric("events_by_type", window_start, window_end, ebt_res)

        # 2.4 Top Products
        tpv_res = calculate_top_viewed_products(valid_events)
        self.publisher.publish_metric("top_products_viewed", window_start, window_end, tpv_res)

        tpp_res = calculate_top_purchased_products(valid_events)
        self.publisher.publish_metric("top_products_purchased", window_start, window_end, tpp_res)

        # 2.5 Purchases By Region
        pbr_res = calculate_purchases_by_region(valid_events)
        self.publisher.publish_metric("purchases_by_region", window_start, window_end, pbr_res)

        # 2.6 Conversion
        conv_res = calculate_conversion(valid_events)
        self.publisher.publish_metric("conversion", window_start, window_end, conv_res)

        # 2.7 Trends
        tr_res = calculate_trends(valid_events)
        self.publisher.publish_metric("trends", window_start, window_end, tr_res)

        # 3. Audiencias (por usuario activo)
        active_users_in_batch = {e["user_id"] for e in valid_events}
        for uid in active_users_in_batch:
            user_history = self.user_events_history.get(uid, [])
            audience_results = self.audience_registry.evaluate_user(uid, user_history)
            for aud in audience_results:
                self.publisher.publish_audience(aud.to_dict())

        # 4. Alertas y Anomalías
        alerts = self.anomaly_detector.detect(valid_events, window_start, window_end)
        for alert in alerts:
            self.publisher.publish_alert(alert)


def main():
    LOGGER.info("Iniciando Flink Job Pipeline (PyFlink Stream Processing)")
    pipeline = FlinkJobPipeline()
    LOGGER.info("Pipeline inicializado y listo para procesar eventos.")


if __name__ == "__main__":
    main()
