import json
from typing import Any, Dict
from agent.tools import generate_invoice


def build_purchase_payload(
    product_id: str,
    quantity: int,
    shipping_address: Dict[str, str],
    buyer_agent_id: str,
) -> Dict[str, Any]:
    return {
        "product_id": product_id,
        "quantity": quantity,
        "buyer_agent_id": buyer_agent_id,
        "delivery_metadata": {
            "shipping_address": shipping_address,
        },
    }


def prepare_checkout_payload(
    product: Dict[str, Any],
    quantity: int,
    buyer_agent_id: str,
    shipping_address: Dict[str, str],
) -> Dict[str, Any]:
    purchase_payload = build_purchase_payload(
        product_id=product["product_id"],
        quantity=quantity,
        shipping_address=shipping_address,
        buyer_agent_id=buyer_agent_id,
    )
    purchase_payload["unit_price_xrp"] = product["unit_price_xrp"]
    purchase_payload["total_price_xrp"] = round(product["unit_price_xrp"] * quantity, 6)
    return purchase_payload


def propose_purchase(product: Dict[str, Any], quantity: int, buyer_agent_id: str, shipping_address: Dict[str, str]) -> Dict[str, Any]:
    payload = prepare_checkout_payload(product, quantity, buyer_agent_id, shipping_address)
    return {
        "status": "prepared",
        "payload": payload,
        "message": f"Prepared checkout parameters for {quantity} x {product['name']}."
    }
