from typing import Any, Dict, List

def calculate_active_users(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Cuenta el número de usuarios activos únicos (DISTINCT user_id) en el conjunto de eventos de la ventana.
    """
    unique_users = {event["user_id"] for event in events if "user_id" in event}
    return {
        "active_users_count": len(unique_users),
        "unique_users_sample": list(unique_users)[:10]
    }
