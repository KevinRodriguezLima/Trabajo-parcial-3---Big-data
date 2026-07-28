from __future__ import annotations

import json
import random
from pathlib import Path

from .config import ScenarioConfig
from .models import Location, Product


class Catalog:
    def __init__(self, products_path: Path, locations_path: Path) -> None:
        self.products = self._load_products(products_path)
        self.locations = self._load_locations(locations_path)
        if not self.products:
            raise ValueError("El catálogo de productos está vacío")
        if not self.locations:
            raise ValueError("El catálogo de ubicaciones está vacío")

    @staticmethod
    def _load_products(path: Path) -> list[Product]:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [
            Product(
                product_id=str(item["product_id"]),
                product_name=str(item["product_name"]),
                category=str(item["category"]),
                base_price=float(item["base_price"]),
                popularity=float(item.get("popularity", 1.0)),
            )
            for item in raw
        ]

    @staticmethod
    def _load_locations(path: Path) -> list[Location]:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [
            Location(
                city=str(item["city"]),
                region=str(item["region"]),
                latitude=float(item["latitude"]),
                longitude=float(item["longitude"]),
                weight=float(item.get("weight", 1.0)),
            )
            for item in raw
        ]

    def choose_location(self, rng: random.Random) -> Location:
        return rng.choices(self.locations, weights=[loc.weight for loc in self.locations], k=1)[0]

    def choose_product(
        self,
        rng: random.Random,
        scenario: ScenarioConfig,
        min_price: float,
        max_price: float,
        preferred_category: str | None = None,
    ) -> Product:
        candidates = [p for p in self.products if min_price <= self.price_for(p, scenario) <= max_price]
        if not candidates:
            candidates = list(self.products)

        weights: list[float] = []
        for product in candidates:
            weight = max(product.popularity, 0.01)
            weight *= scenario.category_boosts.get(product.category, 1.0)
            if preferred_category and product.category == preferred_category:
                weight *= 2.5
            weights.append(weight)
        return rng.choices(candidates, weights=weights, k=1)[0]

    @staticmethod
    def price_for(product: Product, scenario: ScenarioConfig) -> float:
        discount = scenario.discount_by_category.get(product.category, 0.0)
        discount = min(max(discount, 0.0), 0.90)
        return round(product.base_price * (1.0 - discount), 2)
