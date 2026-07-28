from __future__ import annotations

import asyncio
import random
from datetime import datetime

from .catalog import Catalog
from .clock import VirtualClock
from .config import ProfileConfig, ScenarioConfig
from .enums import AgentState, EventType, SourceHint
from .event_factory import EventFactory
from .models import CartItem, GeneratedMessage, Location, Product
from .policy import adjusted_actions, choose_source, profile_activity_multiplier, weighted_choice
from .sinks import EventSink


class Agent:
    def __init__(
        self,
        *,
        user_id: str,
        profile: ProfileConfig,
        scenario: ScenarioConfig,
        catalog: Catalog,
        clock: VirtualClock,
        sink: EventSink,
        seed: int,
    ) -> None:
        self.user_id = user_id
        self.profile = profile
        self.scenario = scenario
        self.catalog = catalog
        self.clock = clock
        self.sink = sink
        self.rng = random.Random(seed)
        self.factory = EventFactory(catalog, scenario, self.rng)
        self.location: Location = catalog.choose_location(self.rng)
        self.state = AgentState.OFFLINE
        self.session_id = ""
        self.cart_id = ""
        self.session_counter = 0
        self.cart_counter = 0
        self.order_counter = 0
        self.cart: dict[str, CartItem] = {}
        self.current_product: Product | None = None
        self.preferred_category: str | None = None
        self.source_hint = SourceHint.WEB
        self.session_started_at: datetime | None = None
        self.has_logged_in = False

    @property
    def current_session_id(self) -> str:
        return self.session_id or f"SES_BG_{self.user_id}"

    def is_active_now(self) -> bool:
        return self.clock.now().hour in self.profile.active_hours

    async def run(self, stop_event: asyncio.Event) -> None:
        await asyncio.sleep(self.rng.uniform(0.0, 0.25))
        while not stop_event.is_set():
            if not self.is_active_now():
                await asyncio.sleep(0.08)
                continue

            activity = self.scenario.activity_multiplier * profile_activity_multiplier(
                self.profile.profile, self.scenario
            )
            if activity <= 0:
                await asyncio.sleep(0.10)
                continue

            if self.state == AgentState.OFFLINE:
                await self._start_session()
                delay = self.rng.uniform(
                    self.profile.offline_delay_min_seconds,
                    self.profile.offline_delay_max_seconds,
                )
            else:
                await self._step()
                delay = self.rng.uniform(
                    self.profile.delay_min_seconds,
                    self.profile.delay_max_seconds,
                )

            await asyncio.sleep(max(0.005, delay / activity))

    async def _start_session(self) -> None:
        self.session_counter += 1
        self.cart_counter += 1
        self.session_id = f"SES_{self.user_id}_{self.session_counter:04d}"
        self.cart_id = f"CART_{self.user_id}_{self.cart_counter:04d}"
        self.cart = {}
        self.current_product = None
        self.preferred_category = None
        self.source_hint = choose_source(self.rng, self.profile)
        self.session_started_at = self.clock.now()
        message = self.factory.build(
            event_type=EventType.LOGIN,
            event_time=self.session_started_at,
            user_id=self.user_id,
            session_id=self.session_id,
            profile=self.profile.profile,
            location=self.location,
            source_hint=self.source_hint,
            payload=self.factory.login_payload(self.source_hint, not self.has_logged_in),
        )
        await self.sink.emit(message)
        self.has_logged_in = True
        self.state = AgentState.HOME

    async def _step(self) -> None:
        if self.state == AgentState.HOME:
            await self._step_home()
        elif self.state == AgentState.PRODUCT:
            await self._step_product()
        elif self.state == AgentState.CART:
            await self._step_cart()
        else:
            self._end_session()

    async def _step_home(self) -> None:
        action = weighted_choice(
            self.rng,
            adjusted_actions(self.profile, self.scenario, AgentState.HOME.value),
        )
        if action == "SEARCH":
            product = self._choose_product()
            self.current_product = product
            self.preferred_category = product.category
            await self._emit(EventType.SEARCH, self.factory.search_payload(product))
            self.state = AgentState.PRODUCT
        elif action == "PAGE_VIEW":
            await self._emit(EventType.PAGE_VIEW, self.factory.page_view_payload())
        else:
            self._end_session()

    async def _step_product(self) -> None:
        if self.current_product is None:
            self.current_product = self._choose_product()
        await self._emit(
            EventType.VIEW_PRODUCT,
            self.factory.view_product_payload(self.current_product),
        )

        action = weighted_choice(
            self.rng,
            adjusted_actions(self.profile, self.scenario, AgentState.PRODUCT.value),
        )
        if action == "ADD_TO_CART":
            await self._add_current_product_to_cart()
            self.state = AgentState.CART
        elif action == "SEARCH":
            product = self._choose_product(preferred_category=self.preferred_category)
            self.current_product = product
            await self._emit(EventType.SEARCH, self.factory.search_payload(product))
            self.state = AgentState.PRODUCT
        elif action == "PAGE_VIEW":
            await self._emit(EventType.PAGE_VIEW, self.factory.page_view_payload())
            self.state = AgentState.HOME
        else:
            self._end_session()

    async def _step_cart(self) -> None:
        if not self.cart:
            self.state = AgentState.HOME
            return
        action = weighted_choice(
            self.rng,
            adjusted_actions(self.profile, self.scenario, AgentState.CART.value),
        )
        if action == "PURCHASE":
            await self._purchase_or_fail()
        elif action == "ADD_TO_CART":
            self.current_product = self._choose_product(preferred_category=self.preferred_category)
            await self._add_current_product_to_cart()
        elif action == "REMOVE_FROM_CART":
            await self._remove_item_from_cart()
        elif action == "SEARCH":
            product = self._choose_product(preferred_category=self.preferred_category)
            self.current_product = product
            await self._emit(EventType.SEARCH, self.factory.search_payload(product))
            self.state = AgentState.PRODUCT
        else:
            # EXIT conserva el carrito hasta que la sesión expira, lo que permite
            # a Flink detectar abandono por ausencia de PURCHASE posterior.
            self._end_session()

    def _choose_product(self, preferred_category: str | None = None) -> Product:
        return self.catalog.choose_product(
            self.rng,
            self.scenario,
            self.profile.min_product_price,
            self.profile.max_product_price,
            preferred_category,
        )

    async def _add_current_product_to_cart(self) -> None:
        if self.current_product is None:
            self.current_product = self._choose_product()
        product = self.current_product
        price = self.catalog.price_for(product, self.scenario)
        if product.product_id in self.cart:
            self.cart[product.product_id].quantity += 1
        else:
            self.cart[product.product_id] = CartItem(product=product, unit_price=price, quantity=1)
        item = self.cart[product.product_id]
        await self._emit(
            EventType.ADD_TO_CART,
            self.factory.add_to_cart_payload(self.cart_id, item, self.cart),
        )

    async def _remove_item_from_cart(self) -> None:
        product_id = self.rng.choice(list(self.cart.keys()))
        item = self.cart[product_id]
        item.quantity -= 1
        if item.quantity <= 0:
            del self.cart[product_id]
        await self._emit(
            EventType.REMOVE_FROM_CART,
            self.factory.remove_from_cart_payload(self.cart_id, product_id, 1, self.cart),
        )
        if not self.cart:
            self.state = AgentState.HOME

    async def _purchase_or_fail(self) -> None:
        if not self.cart or self.session_started_at is None:
            self.state = AgentState.HOME
            return
        self.order_counter += 1
        order_id = f"ORD_{self.user_id}_{self.order_counter:05d}"
        event_time = self.clock.now()
        purchase_payload = self.factory.purchase_payload(
            order_id,
            self.cart_id,
            self.cart,
            self.session_started_at,
            event_time,
        )
        failure_probability = min(
            0.95,
            self.profile.payment_failure_probability * self.scenario.payment_failure_multiplier,
        )
        if self.rng.random() < failure_probability:
            await self._emit(
                EventType.PAYMENT_FAILED,
                self.factory.payment_failed_payload(purchase_payload),
                event_time=event_time,
            )
            self.state = AgentState.CART
        else:
            await self._emit(EventType.PURCHASE, purchase_payload, event_time=event_time)
            self._end_session()

    async def _emit(
        self,
        event_type: EventType,
        payload: dict,
        event_time: datetime | None = None,
    ) -> None:
        message = self.factory.build(
            event_type=event_type,
            event_time=event_time or self.clock.now(),
            user_id=self.user_id,
            session_id=self.current_session_id,
            profile=self.profile.profile,
            location=self.location,
            source_hint=self.source_hint,
            payload=payload,
        )
        await self.sink.emit(message)

    def _end_session(self) -> None:
        self.state = AgentState.OFFLINE
        self.session_id = ""
        self.cart_id = ""
        self.cart = {}
        self.current_product = None
        self.preferred_category = None
        self.session_started_at = None
