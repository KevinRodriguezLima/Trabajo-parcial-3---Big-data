from collections import Counter
from typing import Any, Dict, List

def calculate_events_by_type(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Agrupa y cuenta los eventos por event_type.
    """
    counter = Counter(event.get("event_type", "UNKNOWN") for event in events)
    return {
        "counts": dict(counter),
        "total_events": len(events)
    }
