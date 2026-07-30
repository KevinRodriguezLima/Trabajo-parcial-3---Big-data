from collections import defaultdict
from typing import Any, Dict, List

def calculate_purchases_by_region(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Agrupa y calcula cantidad de compras y monto total acumulado por región.
    """
    regions_summary = defaultdict(lambda: {"purchases_count": 0, "total_amount": 0.0})

    for event in events:
        if event.get("event_type") == "PURCHASE":
            region = event.get("region", "DESCONOCIDA")
            payload = event.get("payload", {})
            total_amount = float(payload.get("total_amount", 0.0))

            regions_summary[region]["purchases_count"] += 1
            regions_summary[region]["total_amount"] += total_amount

    formatted_regions = [
        {
            "region": reg,
            "purchases_count": data["purchases_count"],
            "total_amount": round(data["total_amount"], 2)
        }
        for reg, data in sorted(regions_summary.items(), key=lambda x: x[1]["total_amount"], reverse=True)
    ]

    return {
        "regions": formatted_regions
    }
