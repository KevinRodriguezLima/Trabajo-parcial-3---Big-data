from typing import Any, Dict, List

def calculate_trends(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calcula agregados de serie temporal para tendencias en ventanas deslizantes.
    """
    total_events = len(events)
    unique_users = len({e["user_id"] for e in events if "user_id" in e})
    purchases = [e for e in events if e.get("event_type") == "PURCHASE"]
    purchases_count = len(purchases)
    total_revenue = sum(float(e.get("payload", {}).get("total_amount", 0.0)) for e in purchases)

    return {
        "events_count": total_events,
        "active_users": unique_users,
        "purchases_count": purchases_count,
        "total_revenue": round(total_revenue, 2)
    }
