from collections import defaultdict
from typing import Any, Dict, List

def calculate_top_viewed_products(events: List[Dict[str, Any]], limit: int = 10) -> Dict[str, Any]:
    """
    Obtiene el Top N productos más vistos (event_type == VIEW_PRODUCT).
    """
    view_counts = defaultdict(lambda: {"count": 0, "name": "", "category": ""})
    for event in events:
        if event.get("event_type") == "VIEW_PRODUCT":
            payload = event.get("payload", {})
            p_id = payload.get("product_id")
            if p_id:
                view_counts[p_id]["count"] += 1
                view_counts[p_id]["name"] = payload.get("product_name", "")
                view_counts[p_id]["category"] = payload.get("category", "")

    sorted_views = sorted(
        [
            {
                "product_id": pid,
                "product_name": data["name"],
                "category": data["category"],
                "count": data["count"]
            }
            for pid, data in view_counts.items()
        ],
        key=lambda x: x["count"],
        reverse=True
    )[:limit]

    return {
        "type": "VIEWED",
        "top_products": sorted_views
    }

def calculate_top_purchased_products(events: List[Dict[str, Any]], limit: int = 10) -> Dict[str, Any]:
    """
    Obtiene el Top N productos más comprados (event_type == PURCHASE).
    """
    purchase_counts = defaultdict(lambda: {"count": 0, "total_revenue": 0.0, "name": "", "category": ""})
    for event in events:
        if event.get("event_type") == "PURCHASE":
            payload = event.get("payload", {})
            items = payload.get("items", [])
            for item in items:
                p_id = item.get("product_id")
                if p_id:
                    qty = item.get("quantity", 1)
                    subtotal = item.get("subtotal", 0.0)
                    purchase_counts[p_id]["count"] += qty
                    purchase_counts[p_id]["total_revenue"] += subtotal
                    purchase_counts[p_id]["name"] = item.get("product_name", "")
                    purchase_counts[p_id]["category"] = item.get("category", "")

    sorted_purchases = sorted(
        [
            {
                "product_id": pid,
                "product_name": data["name"],
                "category": data["category"],
                "count": data["count"],
                "total_revenue": round(data["total_revenue"], 2)
            }
            for pid, data in purchase_counts.items()
        ],
        key=lambda x: (x["count"], x["total_revenue"]),
        reverse=True
    )[:limit]

    return {
        "type": "PURCHASED",
        "top_products": sorted_purchases
    }
