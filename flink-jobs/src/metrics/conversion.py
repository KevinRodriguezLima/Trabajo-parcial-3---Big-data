from typing import Any, Dict, List

def calculate_conversion(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calcula el funnel de conversión: VIEW_PRODUCT -> ADD_TO_CART -> PURCHASE.
    """
    views_count = sum(1 for e in events if e.get("event_type") == "VIEW_PRODUCT")
    cart_count = sum(1 for e in events if e.get("event_type") == "ADD_TO_CART")
    purchases_count = sum(1 for e in events if e.get("event_type") == "PURCHASE")

    view_to_cart_rate = round((cart_count / float(views_count)) * 100.0, 2) if views_count > 0 else 0.0
    cart_to_purchase_rate = round((purchases_count / float(cart_count)) * 100.0, 2) if cart_count > 0 else 0.0
    overall_conversion_rate = round((purchases_count / float(views_count)) * 100.0, 2) if views_count > 0 else 0.0

    return {
        "views_count": views_count,
        "cart_additions_count": cart_count,
        "purchases_count": purchases_count,
        "view_to_cart_rate": view_to_cart_rate,
        "cart_to_purchase_rate": cart_to_purchase_rate,
        "overall_conversion_rate": overall_conversion_rate
    }
