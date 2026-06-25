import json
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from langchain_ollama import ChatOllama

from config import OLLAMA_BASE_URL, LLM_MODEL_NAME

llm = ChatOllama(model=LLM_MODEL_NAME, temperature=0, base_url=OLLAMA_BASE_URL)


def _clean_llm_json(content: str) -> str:
    cleaned = content.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[len("```json"):]
    cleaned = cleaned.strip("` \n")
    return cleaned


def fetch_json(url: str) -> Optional[Dict[str, Any]]:
    request = Request(url, headers={"User-Agent": "AgentDiscoveryClient/1.0"})
    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, json.JSONDecodeError):
        return None


def load_merchant_inventory(merchant_manifest_url: str) -> Optional[Dict[str, Any]]:
    manifest = fetch_json(merchant_manifest_url)
    if not manifest:
        return None

    inventory_source = manifest.get("agent_endpoints", {}).get("discovery_inventory_url")
    if inventory_source:
        inventory_url = inventory_source if inventory_source.startswith("http") else urljoin(merchant_manifest_url, inventory_source)
        inventory_manifest = fetch_json(inventory_url)
        if inventory_manifest and inventory_manifest.get("inventory"):
            return inventory_manifest

    if manifest.get("inventory"):
        return manifest

    return None


def _fallback_inventory_match(query: str, inventory: list[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not query:
        return None
    normalized_query = query.strip().lower()
    search_terms = [term for term in normalized_query.split() if len(term) > 2]

    for item in inventory:
        haystack = " ".join(
            str(item.get(key, "")).lower() for key in ["name", "sku", "product_id", "description"]
        )
        if normalized_query in haystack:
            return item

    if search_terms:
        for item in inventory:
            haystack = " ".join(
                str(item.get(key, "")).lower() for key in ["name", "sku", "product_id", "description"]
            )
            if all(term in haystack for term in search_terms):
                return item

    return None


def find_closest_product(query: str, merchant_manifest_url: str) -> Optional[Dict[str, Any]]:
    merchant_inventory = load_merchant_inventory(merchant_manifest_url)
    if not query:
        return None
    if not merchant_inventory:
        return None

    inventory = merchant_inventory.get("inventory", [])
    if not inventory:
        return None

    system_prompt = (
        "You are a product matching assistant. Given a raw user query and a merchant inventory payload, "
        "return the single best matching inventory item as a JSON object. "
        "Respond ONLY with valid JSON and no extra markdown. "
        "If no close match exists, return a JSON object with product_id set to null."
    )

    user_prompt = (
        f"User query: {query}\n"
        f"Merchant inventory:\n{json.dumps(inventory, ensure_ascii=False, indent=2)}\n"
        "Provide the best matching product with the following fields: product_id, sku, name, description, unit_price_xrp, max_autonomous_order_qty, requires_shipping_address, reasoning."
    )

    response = llm.invoke([("system", system_prompt), ("human", user_prompt)])
    clean_text = _clean_llm_json(response.content)

    try:
        product = json.loads(clean_text)
    except json.JSONDecodeError:
        product = None

    if product and product.get("product_id"):
        return product

    fallback = _fallback_inventory_match(query, inventory)
    return fallback


def format_product_summary(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "product_id": item.get("product_id"),
        "sku": item.get("sku"),
        "name": item.get("name"),
        "description": item.get("description", ""),
        "unit_price_xrp": item.get("unit_price_xrp"),
        "max_autonomous_order_qty": item.get("max_autonomous_order_qty", 1),
        "requires_shipping_address": item.get("requires_shipping_address", False),
        "reasoning": item.get("reasoning", ""),
    }
