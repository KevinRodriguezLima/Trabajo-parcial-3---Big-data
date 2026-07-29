from typing import Any, Dict, List

def calculate_throughput(events: List[Dict[str, Any]], window_duration_sec: int) -> Dict[str, Any]:
    """
    Calcula eventos por segundo y total de eventos en una lista de eventos recibidos dentro de la ventana.
    """
    total_events = len(events)
    eps = round(total_events / float(max(1, window_duration_sec)), 2)
    return {
        "events_per_second": eps,
        "total_events": total_events
    }
