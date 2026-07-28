from __future__ import annotations

import random
from datetime import datetime

from .catalog import Catalog
from .config import ScenarioConfig
from .enums import AgentProfile, EventType, Scenario, SourceHint
from .models import CartItem, GeneratedMessage, Location, Product, RawEvent


class EventFactory:
    def __init__(self, catalog: Catalog, scenario: ScenarioConfig, rng: random.Random) -> None:
        self.catalog = catalog
        self.scenario = scenario
        self.rng = rng

    def build(
        self,
        *,
        event_type: EventType,
        event_time: datetime,
        user_id: str,
        session_id: str,
        profile: AgentProfile,
        location: Location,
        source_hint: SourceHint,
        payload: dict,
    ) -> GeneratedMessage:
        event = RawEvent(
            event_type=event_type,
            event_timestamp=event_time.isoformat(timespec="milliseconds"),
            user_id=user_id,
            session_id=session_id,
            agent_profile=profile,
            city=location.city,
            region=location.region,
            scenario=self.scenario.scenario,
            payload=payload,
        )
        return GeneratedMessage(source_hint=source_hint, event=event)

    def login_payload(self, source_hint: SourceHint, is_first_login: bool) -> dict:
        device_by_source = {
            SourceHint.WEB: "WEB_DESKTOP",
            SourceHint.MOBILE: self.rng.choice(["MOBILE_ANDROID", "MOBILE_IOS"]),
            SourceHint.POS: "POS_TERMINAL",
            SourceHint.IOT: "IOT_DEVICE",
            SourceHint.VEHICLE: "VEHICLE_CONSOLE",
        }
        return {
            "device": device_by_source[source_hint],
            "is_first_login": is_first_login,
        }

    def search_payload(self, product: Product) -> dict:
        query_words = product.product_name.lower().split()
        query = " ".join(query_words[: min(len(query_words), self.rng.randint(1, 3))])
        return {
            "query": query,
            "results_count": self.rng.randint(5, 48),
            "category_filter": product.category,
        }

    def page_view_payload(self) -> dict:
        pages = [
            ("HOME", "/"),
            ("OFFERS", "/ofertas"),
            ("CATEGORY", "/categorias"),
            ("SEARCH_RESULTS", "/buscar"),
            ("ACCOUNT", "/mi-cuenta"),
        ]
        page_type, page_url = self.rng.choice(pages)
        return {
            "page_type": page_type,
            "page_url": page_url,
            "dwell_time_ms": self.rng.randint(800, 18000),
        }

    def view_product_payload(self, product: Product) -> dict:
        return {
            "product_id": product.product_id,
            "product_name": product.product_name,
            "category": product.category,
            "price": self.catalog.price_for(product, self.scenario),
            "dwell_time_ms": self.rng.randint(1000, 25000),
        }

    @staticmethod
    def cart_size(cart: dict[str, CartItem]) -> int:
        return sum(item.quantity for item in cart.values())

    @staticmethod
    def cart_value(cart: dict[str, CartItem]) -> float:
        return round(sum(item.subtotal for item in cart.values()), 2)

    def add_to_cart_payload(self, cart_id: str, item: CartItem, cart: dict[str, CartItem]) -> dict:
        return {
            "cart_id": cart_id,
            "product_id": item.product.product_id,
            "product_name": item.product.product_name,
            "category": item.product.category,
            "unit_price": round(item.unit_price, 2),
            "quantity": 1,
            "cart_size_after": self.cart_size(cart),
            "cart_value_after": self.cart_value(cart),
        }

    def remove_from_cart_payload(
        self,
        cart_id: str,
        product_id: str,
        removed_quantity: int,
        cart: dict[str, CartItem],
    ) -> dict:
        return {
            "cart_id": cart_id,
            "product_id": product_id,
            "quantity": removed_quantity,
            "cart_size_after": self.cart_size(cart),
            "cart_value_after": self.cart_value(cart),
        }

    def purchase_payload(
        self,
        order_id: str,
        cart_id: str,
        cart: dict[str, CartItem],
        session_started_at: datetime,
        event_time: datetime,
    ) -> dict:
        items = [
            {
                "product_id": item.product.product_id,
                "product_name": item.product.product_name,
                "category": item.product.category,
                "unit_price": round(item.unit_price, 2),
                "quantity": item.quantity,
                "subtotal": item.subtotal,
            }
            for item in cart.values()
        ]
        total_units = sum(item["quantity"] for item in items)
        total_amount = round(sum(item["subtotal"] for item in items), 2)
        elapsed_ms = max(0, int((event_time - session_started_at).total_seconds() * 1000))
        return {
            "order_id": order_id,
            "cart_id": cart_id,
            "items": items,
            "items_count": len(items),
            "total_units": total_units,
            "total_amount": total_amount,
            "currency": "PEN",
            "payment_method": self.rng.choice(["CREDIT_CARD", "DEBIT_CARD", "YAPE", "PLIN"]),
            "time_to_purchase_ms": elapsed_ms,
        }

    def payment_failed_payload(self, purchase_payload: dict) -> dict:
        return {
            "order_id": purchase_payload["order_id"],
            "cart_id": purchase_payload["cart_id"],
            "total_amount": purchase_payload["total_amount"],
            "payment_method": purchase_payload["payment_method"],
            "failure_reason": self.rng.choice(
                ["INSUFFICIENT_FUNDS", "CARD_EXPIRED", "BANK_REJECTED", "TIMEOUT"]
            ),
            "retry_count": self.rng.randint(1, 3),
        }

    def gps_payload(self, location: Location) -> dict:
        return {
            "device_id": f"DEV_{self.rng.randint(1, 9999):04d}",
            "latitude": round(location.latitude + self.rng.uniform(-0.015, 0.015), 6),
            "longitude": round(location.longitude + self.rng.uniform(-0.015, 0.015), 6),
            "speed_kmh": round(max(0.0, self.rng.gauss(18.0, 14.0)), 1),
        }

    def iot_payload(self) -> dict:
        sensor_type = self.rng.choice(["TEMPERATURE", "HUMIDITY", "LIGHT", "OCCUPANCY"])
        if sensor_type == "TEMPERATURE":
            value, unit = round(self.rng.uniform(12.0, 34.0), 1), "CELSIUS"
        elif sensor_type == "HUMIDITY":
            value, unit = round(self.rng.uniform(25.0, 90.0), 1), "PERCENT"
        elif sensor_type == "LIGHT":
            value, unit = round(self.rng.uniform(50.0, 1200.0), 1), "LUX"
        else:
            value, unit = float(self.rng.randint(0, 50)), "PEOPLE"
        return {
            "device_id": f"SEN_{self.rng.randint(1, 9999):04d}",
            "sensor_type": sensor_type,
            "value": value,
            "unit": unit,
        }

    def motion_payload(self) -> dict:
        return {
            "device_id": f"SEN_{self.rng.randint(1, 9999):04d}",
            "zone": self.rng.choice(
                ["ENTRADA_TIENDA", "CAJA", "TECNOLOGIA", "HOGAR", "ALMACEN"]
            ),
            "confidence": round(self.rng.uniform(0.70, 0.99), 2),
        }

    def social_payload(self, product: Product) -> dict:
        return {
            "platform": self.rng.choice(["INSTAGRAM", "FACEBOOK", "TIKTOK", "X"]),
            "post_type": self.rng.choice(["STORY", "POST", "VIDEO", "COMMENT"]),
            "product_id": product.product_id,
            "sentiment": self.rng.choices(
                ["POSITIVE", "NEUTRAL", "NEGATIVE"], weights=[0.62, 0.28, 0.10], k=1
            )[0],
        }
