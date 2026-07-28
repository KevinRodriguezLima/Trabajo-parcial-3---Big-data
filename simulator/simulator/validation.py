from __future__ import annotations

from typing import Any

from .enums import EventType
from .models import RawEvent


PAYLOAD_REQUIRED_FIELDS: dict[EventType, set[str]] = {
    EventType.LOGIN: {"device", "is_first_login"},
    EventType.SEARCH: {"query", "results_count", "category_filter"},
    EventType.PAGE_VIEW: {"page_type", "page_url", "dwell_time_ms"},
    EventType.VIEW_PRODUCT: {"product_id", "product_name", "category", "price", "dwell_time_ms"},
    EventType.ADD_TO_CART: {
        "cart_id",
        "product_id",
        "product_name",
        "category",
        "unit_price",
        "quantity",
        "cart_size_after",
        "cart_value_after",
    },
    EventType.REMOVE_FROM_CART: {
        "cart_id",
        "product_id",
        "quantity",
        "cart_size_after",
        "cart_value_after",
    },
    EventType.PURCHASE: {
        "order_id",
        "cart_id",
        "items",
        "items_count",
        "total_units",
        "total_amount",
        "currency",
        "payment_method",
        "time_to_purchase_ms",
    },
    EventType.PAYMENT_FAILED: {
        "order_id",
        "cart_id",
        "total_amount",
        "payment_method",
        "failure_reason",
        "retry_count",
    },
    EventType.GPS_UPDATE: {"device_id", "latitude", "longitude", "speed_kmh"},
    EventType.IOT_READING: {"device_id", "sensor_type", "value", "unit"},
    EventType.MOTION_DETECTED: {"device_id", "zone", "confidence"},
    EventType.SOCIAL_POST: {"platform", "post_type", "product_id", "sentiment"},
}


def validate_raw_event(event: RawEvent) -> None:
    if not event.event_timestamp:
        raise ValueError("event_timestamp es obligatorio")
    if not event.user_id:
        raise ValueError("user_id es obligatorio")
    if not event.session_id:
        raise ValueError("session_id es obligatorio en la interfaz A→B")
    if not event.city or not event.region:
        raise ValueError("city y region son obligatorios")
    if not isinstance(event.payload, dict):
        raise TypeError("payload debe ser un objeto")

    required = PAYLOAD_REQUIRED_FIELDS[event.event_type]
    missing = required - set(event.payload)
    if missing:
        raise ValueError(
            f"Payload inválido para {event.event_type.value}; faltan: {sorted(missing)}"
        )

    if event.event_type == EventType.PURCHASE:
        _validate_purchase(event.payload)


def _validate_purchase(payload: dict[str, Any]) -> None:
    items = payload["items"]
    if not isinstance(items, list) or not items:
        raise ValueError("PURCHASE.items debe ser un arreglo no vacío")
    item_required = {"product_id", "product_name", "category", "unit_price", "quantity", "subtotal"}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"PURCHASE.items[{index}] debe ser un objeto")
        missing = item_required - set(item)
        if missing:
            raise ValueError(f"PURCHASE.items[{index}] incompleto: {sorted(missing)}")
