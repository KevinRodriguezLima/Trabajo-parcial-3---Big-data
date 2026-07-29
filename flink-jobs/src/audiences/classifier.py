from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from ..schemas import parse_iso_timestamp
from ..config import CONFIG, AudienceConfig

class AudienceResult:
    def __init__(
        self,
        user_id: str,
        audience_type: str,
        action: str,
        confidence: float,
        evidence: Dict[str, Any],
        detected_at: str,
        expires_at: Optional[str] = None
    ):
        self.user_id = user_id
        self.audience_type = audience_type
        self.action = action
        self.confidence = confidence
        self.evidence = evidence
        self.detected_at = detected_at
        self.expires_at = expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "audience_type": self.audience_type,
            "action": self.action,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "detected_at": self.detected_at,
            "expires_at": self.expires_at
        }


class AudienceRule(ABC):
    """Clase base abstracta para reglas de audiencia pluggables."""
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def evaluate(self, user_id: str, events: List[Dict[str, Any]], config: AudienceConfig) -> Optional[AudienceResult]:
        pass


# 1. Comprador Compulsivo
class CompradorCompulsivoRule(AudienceRule):
    @property
    def name(self) -> str:
        return "COMPRADOR_COMPULSIVO"

    def evaluate(self, user_id: str, events: List[Dict[str, Any]], config: AudienceConfig) -> Optional[AudienceResult]:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=config.compulsivo_window_sec)
        
        purchases = []
        for e in events:
            if e.get("event_type") == "PURCHASE":
                dt = parse_iso_timestamp(e.get("event_timestamp", ""))
                if dt and dt >= cutoff:
                    purchases.append(e)

        if len(purchases) >= config.compulsivo_min_purchases:
            expires_at = (now + timedelta(seconds=config.compulsivo_window_sec)).isoformat()
            return AudienceResult(
                user_id=user_id,
                audience_type=self.name,
                action="ADDED",
                confidence=min(1.0, 0.7 + 0.1 * len(purchases)),
                evidence={"purchases_in_window": len(purchases), "threshold": config.compulsivo_min_purchases},
                detected_at=now.isoformat(),
                expires_at=expires_at
            )
        return None


# 2. Comparador Activo
class ComparadorActivoRule(AudienceRule):
    @property
    def name(self) -> str:
        return "COMPARADOR_ACTIVO"

    def evaluate(self, user_id: str, events: List[Dict[str, Any]], config: AudienceConfig) -> Optional[AudienceResult]:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=config.comparador_window_sec)

        has_cart = any(e.get("event_type") == "ADD_TO_CART" for e in events if parse_iso_timestamp(e.get("event_timestamp", "")) and parse_iso_timestamp(e.get("event_timestamp", "")) >= cutoff)
        if has_cart:
            return None

        viewed_products = set()
        for e in events:
            if e.get("event_type") == "VIEW_PRODUCT":
                dt = parse_iso_timestamp(e.get("event_timestamp", ""))
                if dt and dt >= cutoff:
                    pid = e.get("payload", {}).get("product_id")
                    if pid:
                        viewed_products.add(pid)

        if len(viewed_products) >= config.comparador_min_views:
            expires_at = (now + timedelta(seconds=config.comparador_window_sec)).isoformat()
            return AudienceResult(
                user_id=user_id,
                audience_type=self.name,
                action="ADDED",
                confidence=0.85,
                evidence={"distinct_products_viewed": len(viewed_products), "threshold": config.comparador_min_views},
                detected_at=now.isoformat(),
                expires_at=expires_at
            )
        return None


# 3. Carrito Abandonado
class CarritoAbandonadoRule(AudienceRule):
    @property
    def name(self) -> str:
        return "CARRITO_ABANDONADO"

    def evaluate(self, user_id: str, events: List[Dict[str, Any]], config: AudienceConfig) -> Optional[AudienceResult]:
        now = datetime.now(timezone.utc)
        timeout = timedelta(seconds=config.abandoned_cart_timeout_sec)

        carts = {}  # cart_id -> last_add_time
        purchased_carts = set()

        for e in events:
            etype = e.get("event_type")
            payload = e.get("payload", {})
            cart_id = payload.get("cart_id")
            dt = parse_iso_timestamp(e.get("event_timestamp", ""))

            if etype == "ADD_TO_CART" and cart_id and dt:
                carts[cart_id] = dt
            elif etype == "PURCHASE" and cart_id:
                purchased_carts.add(cart_id)

        abandoned = []
        for cart_id, add_dt in carts.items():
            if cart_id not in purchased_carts and (now - add_dt) >= timeout:
                abandoned.append(cart_id)

        if abandoned:
            return AudienceResult(
                user_id=user_id,
                audience_type=self.name,
                action="ADDED",
                confidence=0.9,
                evidence={"abandoned_carts": abandoned, "timeout_seconds": config.abandoned_cart_timeout_sec},
                detected_at=now.isoformat()
            )
        return None


# 4. Comprador Nocturno
class CompradorNocturnoRule(AudienceRule):
    @property
    def name(self) -> str:
        return "COMPRADOR_NOCTURNO"

    def evaluate(self, user_id: str, events: List[Dict[str, Any]], config: AudienceConfig) -> Optional[AudienceResult]:
        now = datetime.now(timezone.utc)

        night_events = 0
        for e in events:
            dt = parse_iso_timestamp(e.get("event_timestamp", ""))
            if dt:
                hour = dt.hour
                if hour >= config.nocturno_start_hour or hour < config.nocturno_end_hour:
                    night_events += 1

        if night_events >= config.nocturno_min_events:
            return AudienceResult(
                user_id=user_id,
                audience_type=self.name,
                action="ADDED",
                confidence=0.8,
                evidence={"night_events_count": night_events, "threshold": config.nocturno_min_events},
                detected_at=now.isoformat()
            )
        return None


# 5. Usuario Premium / Alto Valor
class UsuarioAltoValorRule(AudienceRule):
    @property
    def name(self) -> str:
        return "USUARIO_ALTO_VALOR"

    def evaluate(self, user_id: str, events: List[Dict[str, Any]], config: AudienceConfig) -> Optional[AudienceResult]:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=config.high_value_window_sec)

        total_spent = 0.0
        for e in events:
            if e.get("event_type") == "PURCHASE":
                dt = parse_iso_timestamp(e.get("event_timestamp", ""))
                if dt and dt >= cutoff:
                    amount = float(e.get("payload", {}).get("total_amount", 0.0))
                    total_spent += amount

        if total_spent >= config.high_value_amount_pen:
            return AudienceResult(
                user_id=user_id,
                audience_type=self.name,
                action="ADDED",
                confidence=0.95,
                evidence={"total_spent_pen": round(total_spent, 2), "threshold_pen": config.high_value_amount_pen},
                detected_at=now.isoformat()
            )
        return None


# 6. Navegador Indeciso
class NavegadorIndecisoRule(AudienceRule):
    @property
    def name(self) -> str:
        return "NAVEGADOR_INDECISO"

    def evaluate(self, user_id: str, events: List[Dict[str, Any]], config: AudienceConfig) -> Optional[AudienceResult]:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=config.indeciso_window_sec)

        cycles = 0
        in_cart = False

        sorted_events = sorted(
            [e for e in events if parse_iso_timestamp(e.get("event_timestamp", "")) and parse_iso_timestamp(e.get("event_timestamp", "")) >= cutoff],
            key=lambda x: parse_iso_timestamp(x["event_timestamp"])
        )

        for e in sorted_events:
            etype = e.get("event_type")
            if etype == "ADD_TO_CART":
                in_cart = True
            elif etype == "REMOVE_FROM_CART" and in_cart:
                cycles += 1
                in_cart = False

        if cycles >= config.indeciso_min_cycles:
            return AudienceResult(
                user_id=user_id,
                audience_type=self.name,
                action="ADDED",
                confidence=0.85,
                evidence={"add_remove_cycles": cycles, "threshold": config.indeciso_min_cycles},
                detected_at=now.isoformat()
            )
        return None


# 7. Usuario Multi-dispositivo
class UsuarioMultiDispositivoRule(AudienceRule):
    @property
    def name(self) -> str:
        return "USUARIO_MULTI_DISPOSITIVO"

    def evaluate(self, user_id: str, events: List[Dict[str, Any]], config: AudienceConfig) -> Optional[AudienceResult]:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=config.multi_device_window_sec)

        sources = set()
        for e in events:
            dt = parse_iso_timestamp(e.get("event_timestamp", ""))
            if dt and dt >= cutoff:
                src = e.get("source")
                if src:
                    sources.add(src)

        if len(sources) >= config.multi_device_min_sources:
            return AudienceResult(
                user_id=user_id,
                audience_type=self.name,
                action="ADDED",
                confidence=0.9,
                evidence={"sources_used": list(sources), "threshold": config.multi_device_min_sources},
                detected_at=now.isoformat()
            )
        return None


class AudienceClassifierRegistry:
    """
    Registro pluggable de audiencias. Permite registrar, eliminar o modificar reglas dinámicamente.
    """
    def __init__(self, config: Optional[AudienceConfig] = None):
        self.config = config or CONFIG.audiences
        self.rules: Dict[str, AudienceRule] = {}
        self.register_default_rules()

    def register(self, rule: AudienceRule):
        self.rules[rule.name] = rule

    def unregister(self, rule_name: str):
        self.rules.pop(rule_name, None)

    def register_default_rules(self):
        self.register(CompradorCompulsivoRule())
        self.register(ComparadorActivoRule())
        self.register(CarritoAbandonadoRule())
        self.register(CompradorNocturnoRule())
        self.register(UsuarioAltoValorRule())
        self.register(NavegadorIndecisoRule())
        self.register(UsuarioMultiDispositivoRule())

    def evaluate_user(self, user_id: str, user_events: List[Dict[str, Any]]) -> List[AudienceResult]:
        results = []
        for rule in self.rules.values():
            res = rule.evaluate(user_id, user_events, self.config)
            if res:
                results.append(res)
        return results
