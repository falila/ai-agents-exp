from typing import Any, Dict
from config import MAX_ALLOWANCE_XRP


def audit_purchase_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    total_price_xrp = payload.get("total_price_xrp", 0)
    issues = []

    if total_price_xrp > MAX_ALLOWANCE_XRP:
        issues.append(f"Exceeded budget limit of {MAX_ALLOWANCE_XRP} XRP.")

    if payload.get("quantity", 0) <= 0:
        issues.append("Quantity must be one or more.")

    if payload.get("delivery_metadata", {}).get("shipping_address", {}) == {}:
        issues.append("Shipping address is required for delivery items.")

    if payload.get("product_id") is None:
        issues.append("Missing product identifier.")

    if issues:
        return {"approved": False, "issues": issues}

    return {"approved": True, "issues": []}
