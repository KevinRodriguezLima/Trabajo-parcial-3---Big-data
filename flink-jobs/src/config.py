import os
from dataclasses import dataclass, field

@dataclass
class WindowConfig:
    """Configuración centralizada de tamaños y deslizamientos de ventanas (en segundos)."""
    throughput_window_sec: int = int(os.getenv("WIN_THROUGHPUT_SEC", "10"))
    active_users_window_sec: int = int(os.getenv("WIN_ACTIVE_USERS_SEC", "60"))
    events_by_type_window_sec: int = int(os.getenv("WIN_EVENTS_BY_TYPE_SEC", "10"))
    top_products_window_sec: int = int(os.getenv("WIN_TOP_PRODUCTS_SEC", "60"))
    purchases_region_window_sec: int = int(os.getenv("WIN_PURCHASES_REGION_SEC", "60"))
    conversion_window_sec: int = int(os.getenv("WIN_CONVERSION_SEC", "60"))
    trends_window_sec: int = int(os.getenv("WIN_TRENDS_SEC", "60"))
    trends_slide_sec: int = int(os.getenv("WIN_TRENDS_SLIDE_SEC", "10"))
    watermark_lateness_sec: int = int(os.getenv("WATERMARK_LATENESS_SEC", "5"))

@dataclass
class AudienceConfig:
    """Configuración de parámetros y umbrales para reglas de audiencias."""
    # 1. Comprador Compulsivo
    compulsivo_min_purchases: int = int(os.getenv("AUD_COMPULSIVO_MIN_PURCHASES", "3"))
    compulsivo_window_sec: int = int(os.getenv("AUD_COMPULSIVO_WINDOW_SEC", "600"))
    
    # 2. Comparador Activo
    comparador_min_views: int = int(os.getenv("AUD_COMPARADOR_MIN_VIEWS", "5"))
    comparador_window_sec: int = int(os.getenv("AUD_COMPARADOR_WINDOW_SEC", "300"))
    
    # 3. Carrito Abandonado
    abandoned_cart_timeout_sec: int = int(os.getenv("AUD_ABANDONED_CART_TIMEOUT_SEC", "900"))
    
    # 4. Comprador Nocturno
    nocturno_min_events: int = int(os.getenv("AUD_NOCTURNO_MIN_EVENTS", "3"))
    nocturno_start_hour: int = int(os.getenv("AUD_NOCTURNO_START_HOUR", "22"))
    nocturno_end_hour: int = int(os.getenv("AUD_NOCTURNO_END_HOUR", "6"))
    
    # 5. Usuario Premium / Alto Valor
    high_value_amount_pen: float = float(os.getenv("AUD_HIGH_VALUE_AMOUNT_PEN", "1000.0"))
    high_value_window_sec: int = int(os.getenv("AUD_HIGH_VALUE_WINDOW_SEC", "3600"))
    
    # 6. Navegador Indeciso
    indeciso_min_cycles: int = int(os.getenv("AUD_INDECISO_MIN_CYCLES", "3"))
    indeciso_window_sec: int = int(os.getenv("AUD_INDECISO_WINDOW_SEC", "1800"))
    
    # 7. Usuario Multi-dispositivo
    multi_device_min_sources: int = int(os.getenv("AUD_MULTI_DEVICE_MIN_SOURCES", "2"))
    multi_device_window_sec: int = int(os.getenv("AUD_MULTI_DEVICE_WINDOW_SEC", "3600"))

@dataclass
class AnomalyConfig:
    """Configuración para la detección de anomalías."""
    spike_multiplier: float = float(os.getenv("ALERT_SPIKE_MULTIPLIER", "3.0"))
    drop_multiplier: float = float(os.getenv("ALERT_DROP_MULTIPLIER", "0.2"))
    payment_fail_threshold_pct: float = float(os.getenv("ALERT_PAYMENT_FAIL_PCT", "20.0"))
    high_cart_threshold: float = float(os.getenv("ALERT_HIGH_CART_PEN", "5000.0"))
    high_latency_threshold_ms: float = float(os.getenv("ALERT_HIGH_LATENCY_MS", "30000.0"))

@dataclass
class FlinkConfig:
    kafka_bootstrap_internal: str = os.getenv("KAFKA_BOOTSTRAP_INTERNAL", "kafka:9092")
    kafka_bootstrap_external: str = os.getenv("KAFKA_BOOTSTRAP_EXTERNAL", "localhost:29092")
    group_id: str = os.getenv("FLINK_GROUP_ID", "flink-audience-processor")
    
    # Postgres configuration for Sink
    postgres_host: str = os.getenv("POSTGRES_HOST", "postgres")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_db: str = os.getenv("POSTGRES_DB", "audiencias")
    postgres_user: str = os.getenv("POSTGRES_USER", "audiencias")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "audiencias")
    
    windows: WindowConfig = field(default_factory=WindowConfig)
    audiences: AudienceConfig = field(default_factory=AudienceConfig)
    anomalies: AnomalyConfig = field(default_factory=AnomalyConfig)

    @property
    def postgres_dsn(self) -> str:
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

CONFIG = FlinkConfig()
