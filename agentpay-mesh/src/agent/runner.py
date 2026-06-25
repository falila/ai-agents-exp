import json
import os
import socket
import time
import uuid
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from agent.concierge import find_closest_product, format_product_summary, load_merchant_inventory
from agent.procurement import prepare_checkout_payload

DEFAULT_MERCHANT_MANIFEST_URL = "http://localhost:8000/ai-agent.json"
MERCHANT_PURCHASE_ENDPOINT = "/api/v1/agent/purchase"
MERCHANT_ORDER_ENDPOINT = "/api/v1/agent/orders/"
MERCHANT_VERIFY_ENDPOINT = "/api/v1/agent/verify"
PURCHASE_REQUEST_TIMEOUT_SECONDS = int(os.getenv("PURCHASE_REQUEST_TIMEOUT_SECONDS", "90"))
PURCHASE_REQUEST_RETRIES = int(os.getenv("PURCHASE_REQUEST_RETRIES", "2"))


def _http_post_json(url: str, body: Dict[str, Any]) -> Dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "ConsumerAgent/1.0"},
        method="POST",
    )
    last_error = None
    for attempt in range(1, PURCHASE_REQUEST_RETRIES + 2):
        try:
            with urlopen(request, timeout=PURCHASE_REQUEST_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = ""
            try:
                raw = exc.read().decode("utf-8")
                payload = json.loads(raw)
                detail = payload.get("detail")
            except Exception:
                detail = ""
            if detail:
                raise RuntimeError(f"Merchant API returned {exc.code}: {detail}")
            raise RuntimeError(f"Merchant API returned {exc.code}")
        except URLError as exc:
            last_error = exc
            is_timeout = isinstance(exc.reason, TimeoutError) or isinstance(exc.reason, socket.timeout)
            if not is_timeout or attempt > PURCHASE_REQUEST_RETRIES + 1:
                break
            time.sleep(min(2 * attempt, 5))

    raise RuntimeError(f"Merchant API request failed: {getattr(last_error, 'reason', 'unknown error')}")


def _http_get_json(url: str) -> Dict[str, Any]:
    request = Request(url, headers={"User-Agent": "ConsumerAgent/1.0"})
    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"Merchant API returned {exc.code}")
    except URLError as exc:
        raise RuntimeError(f"Merchant API request failed: {exc.reason}")


def product_from_selection(selection_id: str, merchant_manifest_url: str = DEFAULT_MERCHANT_MANIFEST_URL) -> Dict[str, Any]:
    merchant_inventory = load_merchant_inventory(merchant_manifest_url)
    if not merchant_inventory:
        raise ValueError("Could not load merchant inventory from manifest URL.")

    inventory = merchant_inventory.get("inventory", [])
    for item in inventory:
        if item.get("product_id") == selection_id or item.get("sku") == selection_id:
            return item
    raise ValueError(f"Product selection '{selection_id}' did not match any local inventory item.")


def chat_search(query: str, merchant_manifest_url: str = DEFAULT_MERCHANT_MANIFEST_URL) -> Dict[str, Any]:
    matched = find_closest_product(query, merchant_manifest_url)
    if not matched:
        return {"query": query, "match": None}

    return {
        "query": query,
        "match": format_product_summary(matched),
    }


def confirm_purchase(
    selection_id: str,
    quantity: int,
    shipping_address: Dict[str, str],
    buyer_agent_id: str,
    merchant_manifest_url: str = DEFAULT_MERCHANT_MANIFEST_URL,
) -> Dict[str, Any]:
    product = product_from_selection(selection_id, merchant_manifest_url)
    payload = prepare_checkout_payload(product, quantity, buyer_agent_id, shipping_address)

    purchase_url = urljoin(merchant_manifest_url, MERCHANT_PURCHASE_ENDPOINT)
    purchase_response = _http_post_json(purchase_url, {
        "product_id": payload["product_id"],
        "quantity": payload["quantity"],
        "buyer_agent_id": payload["buyer_agent_id"],
        "shipping_address": payload["delivery_metadata"]["shipping_address"],
    })

    return {
        "status": purchase_response.get("status", "unknown"),
        "invoice_id": purchase_response.get("invoice_id"),
        "order": purchase_response,
        "payload": payload,
    }


def get_order_status(invoice_id: str, merchant_manifest_url: str = DEFAULT_MERCHANT_MANIFEST_URL) -> Dict[str, Any]:
    order_url = urljoin(merchant_manifest_url, MERCHANT_ORDER_ENDPOINT + invoice_id)
    return _http_get_json(order_url)
