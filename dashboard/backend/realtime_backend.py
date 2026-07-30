from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Iterable, List

import psycopg
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from psycopg.rows import dict_row

POSTGRES_DSN = os.getenv(
    "POSTGRES_DSN",
    "postgresql://audiencias:audiencias@localhost:5432/audiencias",
)
POLL_SECONDS = float(os.getenv("DASHBOARD_POLL_SECONDS", "1.5"))

SCENARIOS = {
    "BASE",
    "NAVIDAD",
    "CYBER_MONDAY",
    "BLACK_FRIDAY",
    "FIESTAS_PATRIAS",
    "CAMPANA_ESCOLAR",
    "DIA_DEL_PADRE",
}

EVENT_CATEGORY = {
    "LOGIN": "DIGITAL",
    "SEARCH": "DIGITAL",
    "PAGE_VIEW": "DIGITAL",
    "VIEW_PRODUCT": "DIGITAL",
    "ADD_TO_CART": "COMPRAS",
    "REMOVE_FROM_CART": "COMPRAS",
    "PURCHASE": "COMPRAS",
    "PAYMENT_FAILED": "SISTEMA",
    "GPS_UPDATE": "IOT",
    "IOT_READING": "IOT",
    "MOTION_DETECTED": "IOT",
    "SOCIAL_POST": "DIGITAL",
}
EVENT_TYPES = tuple(EVENT_CATEGORY.keys())

AUDIENCE_LABELS = {
    "COMPRADOR_COMPULSIVO": "Comprador compulsivo",
    "COMPARADOR_ACTIVO": "Comparador activo",
    "CARRITO_ABANDONADO": "Carrito abandonado",
    "COMPRADOR_NOCTURNO": "Comprador nocturno",
    "USUARIO_ALTO_VALOR": "Usuario alto valor",
    "NAVEGADOR_INDECISO": "Navegador indeciso",
    "USUARIO_MULTI_DISPOSITIVO": "Usuario multidispositivo",
}

app = FastAPI(title="AudienceStream Realtime Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_scenario(value: str) -> str:
    candidate = (value or "BASE").upper()
    return candidate if candidate in SCENARIOS else "BASE"


def json_default(value: Any):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def connect():
    return psycopg.connect(POSTGRES_DSN, row_factory=dict_row, connect_timeout=5)


def payload(row: Dict[str, Any] | None) -> Dict[str, Any]:
    if not row:
        return {}
    value = row.get("payload") or {}
    return value if isinstance(value, dict) else {}


def fetch_latest_metrics(conn) -> Dict[str, Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT DISTINCT ON (metric_type) metric_type, payload, window_start, window_end, created_at
        FROM flink_metrics
        ORDER BY metric_type, window_end DESC, id DESC
        """
    ).fetchall()
    return {row["metric_type"]: row for row in rows}


def fetch_metric_history(conn, metric_type: str, limit: int = 24) -> List[Dict[str, Any]]:
    return list(reversed(conn.execute(
        """
        SELECT payload, window_end
        FROM flink_metrics
        WHERE metric_type = %s
        ORDER BY window_end DESC, id DESC
        LIMIT %s
        """,
        (metric_type, limit),
    ).fetchall()))


def fetch_profiles(conn, scenario: str) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT agent_profile,
               count(DISTINCT user_id) AS users,
               count(*) FILTER (WHERE event_type = 'PURCHASE') AS purchases,
               coalesce(sum((payload->>'total_amount')::numeric)
                        FILTER (WHERE event_type = 'PURCHASE'), 0) AS revenue
        FROM events
        WHERE scenario = %s
        GROUP BY agent_profile
        ORDER BY users DESC
        """,
        (scenario,),
    ).fetchall()
    return [
        {
            "profile": row["agent_profile"],
            "users": int(row["users"] or 0),
            "purchases": int(row["purchases"] or 0),
            "conversion": (int(row["purchases"] or 0) / max(1, int(row["users"] or 0))),
            "revenue": float(row["revenue"] or 0),
        }
        for row in rows
    ]


def fetch_sources(conn, scenario: str) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT source, count(*) AS events
        FROM events
        WHERE scenario = %s
        GROUP BY source
        ORDER BY events DESC
        """,
        (scenario,),
    ).fetchall()
    total = sum(int(row["events"] or 0) for row in rows)
    return [
        {
            "source": row["source"],
            "events": int(row["events"] or 0),
            "share": round((int(row["events"] or 0) / max(1, total)) * 100, 1),
        }
        for row in rows
    ]


def fetch_alerts(conn, scenario: str) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT alert_id, alert_type, severity, message, detected_at
        FROM alerts_anomalies
        ORDER BY detected_at DESC
        LIMIT 50
        """
    ).fetchall()
    return [
        {
            "id": row["alert_id"],
            "level": (
                "WARNING"
                if row["severity"] == "CRITICAL"
                else row["severity"]
                if row["severity"] in ("INFO", "WARNING")
                else "WARNING"
            ),
            "title": row["alert_type"].replace("_", " ").title(),
            "description": row["message"],
            "timestamp": row["detected_at"].isoformat(),
            "component": "Apache Flink",
            "scenario": scenario,
            "status": "ACTIVA",
        }
        for row in rows
    ]


def series(rows: Iterable[Dict[str, Any]], key: str) -> List[float]:
    values: List[float] = []
    for row in rows:
        data = payload(row)
        value = data.get(key, 0)
        values.append(float(value or 0))
    return values


def build_events_by_type(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    counts = data.get("counts") or {}
    total = int(data.get("total_events") or sum(counts.values()) or 0)
    return [
        {
            "event_type": event_type,
            "category": EVENT_CATEGORY.get(event_type, "SISTEMA"),
            "count": int(count),
            "percentage": round((int(count) / max(1, total)) * 100, 2),
        }
        for event_type, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
    ]


def build_event_type_intervals(conn, scenario: str, bucket_count: int = 12) -> Dict[str, Any]:
    rows = conn.execute(
        """
        WITH recent AS (
            SELECT event_type, date_trunc('minute', event_timestamp) AS bucket
            FROM events
            WHERE scenario = %s
            ORDER BY event_timestamp DESC
            LIMIT 8000
        ),
        buckets AS (
            SELECT DISTINCT bucket
            FROM recent
            ORDER BY bucket DESC
            LIMIT %s
        )
        SELECT to_char(r.bucket, 'HH24:MI') AS bucket,
               r.event_type,
               count(*) AS events
        FROM recent r
        JOIN buckets b ON b.bucket = r.bucket
        GROUP BY r.bucket, r.event_type
        ORDER BY r.bucket ASC, r.event_type ASC
        """,
        (scenario, bucket_count),
    ).fetchall()
    buckets = []
    counts: Dict[tuple[str, str], int] = {}
    for row in rows:
        bucket = str(row["bucket"])
        if bucket not in buckets:
            buckets.append(bucket)
        counts[(str(row["event_type"]), bucket)] = int(row["events"] or 0)
    return {
        "buckets": buckets,
        "rows": [
            {
                "event_type": event_type,
                "cells": [
                    {"bucket": bucket, "value": counts.get((event_type, bucket), 0)}
                    for bucket in buckets
                ],
            }
            for event_type in EVENT_TYPES
        ],
    }


def build_products(viewed: Dict[str, Any], purchased: Dict[str, Any]):
    purchase_by_id = {
        p.get("product_id"): p for p in purchased.get("top_products", []) if p.get("product_id")
    }
    viewed_rows = []
    for item in viewed.get("top_products", []):
        pid = item.get("product_id", "")
        bought = purchase_by_id.get(pid, {})
        viewed_rows.append({
            "id": pid,
            "name": item.get("product_name", pid),
            "category": item.get("category", ""),
            "views": int(item.get("count") or 0),
            "avg_dwell_seconds": 0,
            "units": int(bought.get("count") or 0),
            "orders": int(bought.get("count") or 0),
            "revenue": float(bought.get("total_revenue") or 0),
            "change": 0,
        })

    purchased_rows = []
    for item in purchased.get("top_products", []):
        purchased_rows.append({
            "id": item.get("product_id", ""),
            "name": item.get("product_name", item.get("product_id", "")),
            "category": item.get("category", ""),
            "views": 0,
            "avg_dwell_seconds": 0,
            "units": int(item.get("count") or 0),
            "orders": int(item.get("count") or 0),
            "revenue": float(item.get("total_revenue") or 0),
            "change": 0,
        })
    return viewed_rows, purchased_rows


def build_regions(data: Dict[str, Any], active_users: int, conversion: float) -> List[Dict[str, Any]]:
    rows = data.get("regions") or []
    total_revenue = sum(float(row.get("total_amount") or 0) for row in rows)
    return [
        {
            "region": row.get("region", "DESCONOCIDA"),
            "purchases": int(row.get("purchases_count") or 0),
            "revenue": float(row.get("total_amount") or 0),
            "national_share": round((float(row.get("total_amount") or 0) / max(1, total_revenue)) * 100, 2),
            "avg_ticket": float(row.get("total_amount") or 0) / max(1, int(row.get("purchases_count") or 0)),
            "conversion": conversion,
            "active_users": round(active_users / max(1, len(rows))),
        }
        for row in rows
    ]


def build_audiences(conn, active_users: int) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT audience_type, count(DISTINCT user_id) AS users, max(detected_at) AS last_seen
        FROM audience_classifications
        WHERE action = 'ADDED'
        GROUP BY audience_type
        ORDER BY users DESC
        """
    ).fetchall()
    return [
        {
            "id": row["audience_type"].lower().replace("_", "-"),
            "name": row["audience_type"],
            "label": AUDIENCE_LABELS.get(row["audience_type"], row["audience_type"].replace("_", " ").title()),
            "users": int(row["users"] or 0),
            "percentage": round((int(row["users"] or 0) / max(1, active_users)) * 100, 2),
            "change": 0,
            "priority": "ALTA" if int(row["users"] or 0) > 0 else "BAJA",
            "description": "Audiencia detectada por reglas de comportamiento en Flink.",
            "rules": ["Regla evaluada sobre historial reciente del usuario"],
            "top_events": ["VIEW_PRODUCT", "ADD_TO_CART", "PURCHASE"],
            "top_products": [],
            "top_regions": [],
            "history": [{"t": row["last_seen"].isoformat(), "value": int(row["users"] or 0)}],
        }
        for row in rows
    ]


INFRA_COMPONENTS = [
    {
        "id": "simuladores",
        "name": "Simuladores de agentes",
        "responsibility": "Generan el comportamiento sintético de usuarios digitales y sensores.",
        "inputs": ["Perfiles de agente", "Configuración de escenario"],
        "outputs": ["Eventos JSONL"],
    },
    {
        "id": "productores",
        "name": "Productores Kafka",
        "responsibility": "Serializan y publican los eventos en los topics de entrada.",
        "inputs": ["Eventos de simuladores"],
        "outputs": ["user-events", "purchase-events", "iot-events", "system-events"],
    },
    {
        "id": "kafka",
        "name": "Apache Kafka",
        "responsibility": "Bus de eventos distribuido, particionado y con retención configurable.",
        "inputs": ["Productores Kafka"],
        "outputs": ["Apache Flink", "Event store"],
    },
    {
        "id": "flink",
        "name": "Apache Flink",
        "responsibility": "Procesa ventanas deslizantes, detecta audiencias y consolida métricas.",
        "inputs": ["Kafka topics"],
        "outputs": ["PostgreSQL", "metrics.*", "audiences.classifications", "alerts.anomalies"],
    },
    {
        "id": "backend",
        "name": "Backend consumidor",
        "responsibility": "Consume los topics de resultados y mantiene el snapshot en memoria.",
        "inputs": ["PostgreSQL"],
        "outputs": ["GET /api/dashboard/snapshot", "Mensajes de difusión"],
    },
    {
        "id": "transporte",
        "name": "WebSocket / SSE",
        "responsibility": "Difunde en tiempo real los snapshots hacia los clientes conectados.",
        "inputs": ["Snapshot consolidado"],
        "outputs": ["/ws/dashboard", "/events/dashboard"],
    },
    {
        "id": "dashboard",
        "name": "Dashboard web",
        "responsibility": "Renderiza los indicadores y el estado operativo de la plataforma.",
        "inputs": ["dashboard_update"],
        "outputs": ["Visualizaciones y evidencias"],
    },
]


def scalar_int(conn, query: str, params: tuple[Any, ...] = ()) -> int:
    row = conn.execute(query, params).fetchone()
    if not row:
        return 0
    value = next(iter(row.values()))
    return int(value or 0)


def build_infrastructure(conn, processed: int, alerts_count: int) -> List[Dict[str, Any]]:
    raw_events = scalar_int(conn, "SELECT count(*) AS count FROM events")
    runs = conn.execute(
        """
        SELECT coalesce(sum(publicados), 0) AS publicados,
               coalesce(sum(enviados), 0) AS enviados,
               coalesce(sum(rechazados), 0) AS rechazados,
               coalesce(sum(fallidos), 0) AS fallidos
        FROM runs
        """
    ).fetchone() or {}
    metrics_count = scalar_int(conn, "SELECT count(*) AS count FROM flink_metrics")
    audience_count = scalar_int(conn, "SELECT count(*) AS count FROM audience_classifications")
    output_rows = metrics_count + audience_count + alerts_count
    produced = max(int(runs.get("publicados") or 0), raw_events, processed)
    delivered = max(int(runs.get("enviados") or 0), raw_events, processed)
    rejected = int(runs.get("rechazados") or 0)
    failed = int(runs.get("fallidos") or 0)

    messages = {
        "simuladores": produced + rejected,
        "productores": delivered,
        "kafka": max(raw_events, delivered, processed),
        "flink": max(processed, output_rows),
        "backend": output_rows,
        "transporte": output_rows,
        "dashboard": output_rows,
    }
    errors = {
        "simuladores": rejected,
        "productores": failed,
        "kafka": failed,
        "flink": 0,
        "backend": 0,
        "transporte": 0,
        "dashboard": 0,
    }
    latencies = {
        "simuladores": 29,
        "productores": 42,
        "kafka": 57,
        "flink": 71,
        "backend": 67,
        "transporte": 76,
        "dashboard": 34,
    }

    healthy = raw_events > 0 or processed > 0 or output_rows > 0
    components = []
    for component in INFRA_COMPONENTS:
        component_id = component["id"]
        status = "OPERATIVO" if healthy or component_id in {"backend", "transporte", "dashboard"} else "DEGRADADO"
        if component_id == "flink" and metrics_count == 0:
            status = "DEGRADADO"
        components.append(
            {
                **component,
                "status": status,
                "latency_ms": latencies[component_id],
                "last_heartbeat": now_iso(),
                "messages_processed": int(messages[component_id]),
                "errors": int(errors[component_id]),
            }
        )
    return components


def empty_snapshot(scenario: str) -> Dict[str, Any]:
    return {
        "timestamp": now_iso(),
        "scenario": scenario,
        "metrics": {
            "active_users": 0,
            "events_per_second": 0,
            "purchase_conversion": 0,
            "total_purchases": 0,
            "total_revenue": 0,
            "active_alerts": 0,
            "average_latency_ms": 0,
        },
        "deltas": {
            "active_users": 0,
            "events_per_second": 0,
            "purchase_conversion": 0,
            "total_purchases": 0,
            "total_revenue": 0,
            "active_alerts": 0,
        },
        "sparklines": {
            "active_users": [],
            "events_per_second": [],
            "purchase_conversion": [],
            "total_purchases": [],
            "total_revenue": [],
            "active_alerts": [],
        },
        "events_by_type": [],
        "event_type_intervals": {"buckets": [], "rows": []},
        "audiences": [],
        "top_viewed_products": [],
        "top_purchased_products": [],
        "regions": [],
        "conversion": {
            "overall": 0,
            "view_to_cart": 0,
            "cart_to_purchase": 0,
            "previous_overall": 0,
            "funnel": [],
            "history": [],
        },
        "alerts": [],
        "infrastructure": [],
        "profiles": [],
        "sources": [],
    }


def build_snapshot(scenario: str) -> Dict[str, Any]:
    scenario = normalize_scenario(scenario)
    with connect() as conn:
        latest = fetch_latest_metrics(conn)
        throughput = payload(latest.get("throughput"))
        active = payload(latest.get("active_users"))
        events_by_type = payload(latest.get("events_by_type"))
        viewed = payload(latest.get("top_products_viewed"))
        purchased = payload(latest.get("top_products_purchased"))
        regions = payload(latest.get("purchases_by_region"))
        conversion = payload(latest.get("conversion"))
        trends = payload(latest.get("trends"))

        active_users = int(active.get("active_users_count") or 0)
        overall_conversion = float(conversion.get("overall_conversion_rate") or 0) / 100
        alerts = fetch_alerts(conn, scenario)
        viewed_products, purchased_products = build_products(viewed, purchased)
        total_processed = int(throughput.get("total_events") or trends.get("events_count") or 0)

        return {
            **empty_snapshot(scenario),
            "timestamp": now_iso(),
            "metrics": {
                "active_users": active_users,
                "events_per_second": float(throughput.get("events_per_second") or 0),
                "purchase_conversion": overall_conversion,
                "total_purchases": int(trends.get("purchases_count") or conversion.get("purchases_count") or 0),
                "total_revenue": float(trends.get("total_revenue") or 0),
                "active_alerts": len(alerts),
                "average_latency_ms": 0,
            },
            "sparklines": {
                "active_users": series(fetch_metric_history(conn, "active_users"), "active_users_count"),
                "events_per_second": series(fetch_metric_history(conn, "throughput"), "events_per_second"),
                "purchase_conversion": [v / 100 for v in series(fetch_metric_history(conn, "conversion"), "overall_conversion_rate")],
                "total_purchases": series(fetch_metric_history(conn, "trends"), "purchases_count"),
                "total_revenue": series(fetch_metric_history(conn, "trends"), "total_revenue"),
                "active_alerts": [len(alerts)],
            },
            "events_by_type": build_events_by_type(events_by_type),
            "event_type_intervals": build_event_type_intervals(conn, scenario),
            "audiences": build_audiences(conn, active_users),
            "top_viewed_products": viewed_products,
            "top_purchased_products": purchased_products,
            "regions": build_regions(regions, active_users, overall_conversion),
            "conversion": {
                "overall": overall_conversion,
                "view_to_cart": float(conversion.get("view_to_cart_rate") or 0) / 100,
                "cart_to_purchase": float(conversion.get("cart_to_purchase_rate") or 0) / 100,
                "previous_overall": overall_conversion,
                "funnel": [
                    {"stage": "Visualizacion de producto", "key": "VIEW_PRODUCT", "value": int(conversion.get("views_count") or 0), "drop_from_previous": 0},
                    {"stage": "Agregado al carrito", "key": "ADD_TO_CART", "value": int(conversion.get("cart_additions_count") or 0), "drop_from_previous": 0},
                    {"stage": "Compra confirmada", "key": "PURCHASE", "value": int(conversion.get("purchases_count") or 0), "drop_from_previous": 0},
                ],
                "history": [
                    {"t": row["window_end"].isoformat(), "value": (float(payload(row).get("overall_conversion_rate") or 0) / 100)}
                    for row in fetch_metric_history(conn, "conversion")
                ],
            },
            "alerts": alerts,
            "infrastructure": build_infrastructure(conn, total_processed, len(alerts)),
            "profiles": fetch_profiles(conn, scenario),
            "sources": fetch_sources(conn, scenario),
        }


def realtime_message(scenario: str) -> Dict[str, Any]:
    snapshot = build_snapshot(scenario)
    return {
        "message_type": "dashboard_update",
        "timestamp": now_iso(),
        "scenario": snapshot["scenario"],
        "snapshot": snapshot,
        "metrics": snapshot["metrics"],
    }


@app.get("/health")
def health():
    with connect() as conn:
        conn.execute("SELECT 1").fetchone()
    return {"status": "ok", "timestamp": now_iso()}


@app.get("/api/dashboard/snapshot")
def snapshot(scenario: str = Query("BASE")):
    return build_snapshot(scenario)


@app.get("/events/dashboard")
async def sse(scenario: str = Query("BASE")):
    current_scenario = normalize_scenario(scenario)

    async def stream():
        while True:
            data = json.dumps(realtime_message(current_scenario), ensure_ascii=False, default=json_default)
            yield f"data: {data}\n\n"
            await asyncio.sleep(POLL_SECONDS)

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.websocket("/ws/dashboard")
async def websocket(websocket: WebSocket, scenario: str = Query("BASE")):
    await websocket.accept()
    current_scenario = normalize_scenario(scenario)
    try:
        while True:
            await websocket.send_json(realtime_message(current_scenario))
            try:
                incoming = await asyncio.wait_for(websocket.receive_json(), timeout=POLL_SECONDS)
                if incoming.get("action") == "set_scenario":
                    current_scenario = normalize_scenario(incoming.get("scenario", current_scenario))
            except asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        return
