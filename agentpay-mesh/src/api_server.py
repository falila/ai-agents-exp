import os
import asyncio
import json
import time
import hmac
import hashlib
import uuid
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, status, Query, Request
from pydantic import BaseModel
import xrpl
from xrpl.clients import JsonRpcClient
from config import (
    WEBHOOK_SHARED_SECRET,
    XRPL_NETWORK_URL,
    CONSUMER_WALLET_SECRET,
    CONSUMER_WALLET_ADDRESS,
)
from db import (
    initialize_history_db,
    initialize_orders_db,
    insert_pending_order,
    fetch_order_by_invoice,
    fetch_pending_orders,
    update_order_status,
    record_settlement_history,
)
from agent.graph import procurement_agent_node, risk_auditor_agent_node
from agent.tools import trigger_agent_delivery_webhook, settle_consumer_payment_payload, build_presigned_consumer_payment_payload

# Initialize FastAPI instance
app = FastAPI(
    title="PayWithAgent Gateway API",
    description="Machine-to-Machine commerce routing endpoints over the XRP Ledger",
    version="1.0.0"
)

xrpl_client = JsonRpcClient(XRPL_NETWORK_URL)

@app.on_event("startup")
def initialize_databases():
    initialize_history_db()
    initialize_orders_db()

# Helper function to dynamically load the unified manifest data
def load_manifest():
    manifest_path = os.path.join(os.path.dirname(__file__), "ai-agent.json")
    with open(manifest_path, "r") as f:
        return json.load(f)


def resolve_merchant_destination(manifest: Dict[str, Any]) -> str:
    profile = manifest.get("settlement_profile", {})
    return (profile.get("merchant_receiving_address") or "").strip()

# Request Data Validation Schemas
class InvoiceRequest(BaseModel):
    product_id: str
    quantity: int = 1
    buyer_agent_id: str

class PurchaseRequest(BaseModel):
    product_id: str
    quantity: int = 1
    buyer_agent_id: str
    shipping_address: Dict[str, Any]

# ===================================================
# ENDPOINT 1: DISCOVERY MANIFEST
# ===================================================
@app.get("/ai-agent.json", tags=["Discovery"])
async def get_discovery_manifest():
    """Exposes business operational profiles and inventory arrays to scraping AI bots."""
    try:
        return load_manifest()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read manifest profile: {str(e)}"
        )

# ===================================================
# ENDPOINT 2: INVOICE GENERATOR
# ===================================================
@app.post("/api/v1/agent/invoice", status_code=status.HTTP_201_CREATED, tags=["Commerce"])
async def create_agent_invoice(payload: InvoiceRequest):
    """Locks in target item pricing rules and generates a cryptographically sound payment intent."""
    manifest = load_manifest()
    inventory = manifest.get("inventory", [])
    
    # Locate requested target item tracking metrics
    target_item = next((item for item in inventory if item["product_id"] == payload.product_id), None)
    
    if not target_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requested product_id '{payload.product_id}' does not exist in the active store inventory."
        )
        
    # Guardrail: Check maximum allow volumes
    if payload.quantity > 10:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Quantity requested is higher than allowed autonomous limits."
        )

    price_xrp = target_item["unit_price_xrp"] * payload.quantity
    price_drops = int(price_xrp * 1_000_000)
    
    destination_address = resolve_merchant_destination(manifest)
    if not destination_address:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Merchant destination address is missing in ai-agent.json (settlement_profile.merchant_receiving_address).",
        )

    return {
        "status": "success",
        "invoice_id": f"INV-{int(time.time())}",
        "product_id": payload.product_id,
        "price_xrp": price_xrp,
        "price_drops": price_drops,
        "destination_address": destination_address,
        "expires_in_seconds": 600
    }


# ===================================================
# ENDPOINT 2: PURCHASE ORDER
# ===================================================
@app.post("/api/v1/agent/purchase", status_code=status.HTTP_201_CREATED, tags=["Commerce"])
async def create_agent_purchase(payload: PurchaseRequest):
    manifest = load_manifest()
    inventory = manifest.get("inventory", [])
    target_item = next((item for item in inventory if item["product_id"] == payload.product_id), None)

    if not target_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requested product_id '{payload.product_id}' does not exist in inventory."
        )

    state = {
        "target_product_id": payload.product_id,
        "inventory_metadata": manifest,
        "invoice_id": None,
        "price_drops": None,
        "procurement_decision": None,
        "auditor_approved": None,
        "rejection_reason": None,
        "xrpl_tx_hash": None,
        "quantity": payload.quantity,
        "buyer_agent_id": payload.buyer_agent_id,
        "shipping_address": payload.shipping_address,
    }

    procurement_result = procurement_agent_node(state)
    if procurement_result.get("procurement_decision") != "PROCEED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "blocked",
                "reason": procurement_result.get("rejection_reason", "Procurement validation failed."),
            },
        )

    state.update(procurement_result)
    risk_result = risk_auditor_agent_node(state)
    if not risk_result.get("auditor_approved"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "blocked",
                "issues": [risk_result.get("rejection_reason", "Risk auditor denied the purchase.")],
            },
        )

    price_xrp = target_item["unit_price_xrp"] * payload.quantity
    destination_address = resolve_merchant_destination(manifest)
    try:
        presigned_payment_payload = await asyncio.to_thread(
            build_presigned_consumer_payment_payload,
            xrpl_client,
            CONSUMER_WALLET_SECRET,
            CONSUMER_WALLET_ADDRESS,
            destination_address,
            procurement_result["price_drops"],
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"payment_payload_error": str(exc)})

    order = {
        "created_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        "invoice_id": procurement_result["invoice_id"],
        "product_id": payload.product_id,
        "quantity": payload.quantity,
        "buyer_agent_id": payload.buyer_agent_id,
        "thread_id": f"thread-{uuid.uuid4().hex[:8]}",
        "shipping_address": json.dumps(payload.shipping_address),
        "payment_payload": json.dumps(presigned_payment_payload),
        "price_drops": procurement_result["price_drops"],
        "amount_xrp": price_xrp,
        "merchant_address": destination_address,
        "status": "AWAITING_RELEASE",
        "note": "Procurement and risk audit approved; awaiting merchant release.",
    }
    insert_pending_order(order)

    return {
        "status": "AWAITING_RELEASE",
        "invoice_id": procurement_result["invoice_id"],
        "product_id": payload.product_id,
        "quantity": payload.quantity,
        "price_xrp": price_xrp,
        "price_drops": procurement_result["price_drops"],
        "merchant_address": destination_address,
        "buyer_agent_id": payload.buyer_agent_id,
        "shipping_address": payload.shipping_address,
        "payment_payload_presigned": True,
        "payment_payload": presigned_payment_payload,
        "message": "Purchase order created and approved by procurement + risk auditor. Awaiting merchant release.",
    }


# ===================================================
# ENDPOINT 3: ORDER STATUS
# ===================================================
@app.get("/api/v1/agent/orders/{invoice_id}", tags=["Orders"])
async def get_order(invoice_id: str):
    order = fetch_order_by_invoice(invoice_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    return order


@app.get("/api/v1/agent/orders", tags=["Orders"])
async def list_orders():
    return fetch_pending_orders()


# ===================================================
# ENDPOINT 4: RELEASE ORDER
# ===================================================
@app.post("/api/v1/agent/release/{invoice_id}", tags=["Commerce"])
async def release_order(invoice_id: str):
    manifest = load_manifest()
    order = fetch_order_by_invoice(invoice_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    if order["status"] == "SETTLED":
        return {"status": "SETTLED", "message": "Order already settled."}

    raw_payload = order.get("payment_payload") or "{}"
    try:
        payment_payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid payment payload JSON: {exc}")

    if not payment_payload:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot release funds: no consumer payment payload was submitted for this order.",
        )

    try:
        tx_hash = await asyncio.to_thread(
            settle_consumer_payment_payload,
            xrpl_client,
            payment_payload,
            order["merchant_address"],
            order["price_drops"],
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"XRPL settlement failed: {exc}")

    update_order_status(invoice_id, "SETTLED", tx_hash=tx_hash, note="Merchant released funds.")

    record_settlement_history(
        frozen={
            "invoice_id": invoice_id,
            "target_product_id": order["product_id"],
            "price_drops": order["price_drops"],
        },
        tx_hash=tx_hash,
        webhook_url=manifest.get("agent_endpoints", {}).get("webhook_delivery_notification_url", ""),
        thread_id=order.get("thread_id", invoice_id),
        merchant_address=order["merchant_address"],
    )

    return {"status": "SETTLED", "invoice_id": invoice_id, "tx_hash": tx_hash}

# ===================================================
# ENDPOINT 3: SETTLEMENT VERIFICATION
# ===================================================
@app.get("/api/v1/agent/verify", tags=["Settlement"])
async def verify_ledger_settlement(
    tx_hash: str = Query(..., description="The unique on-chain transaction hash block"),
    invoice_id: str = Query(..., description="The corresponding invoice reference string")
):
    """Queries the XRP Ledger directly to validate payment finality status."""
    try:
        # Fetch actual transaction metrics using the live ledger network client lookup wrappers
        tx_response = xrpl.transaction.get_transaction_from_hash(tx_hash, xrpl_client)
        tx_result = tx_response.result
        
        # Verify transaction parameters confirm finality successfully
        if tx_result.get("validated") is True and tx_result.get("meta", {}).get("TransactionResult") == "tesSUCCESS":
            return {
                "status": "settled",
                "invoice_id": invoice_id,
                "ledger_index": tx_result.get("ledger_index"),
                "amount_received_drops": tx_result.get("Amount"),
                "validated": True,
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }
            
        return {
            "status": "pending",
            "invoice_id": invoice_id,
            "message": "Transaction found on ledger but awaiting structural validation confirmation."
        }
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The transaction hash was not found on-chain or ledger indexing timed out."
        )



@app.post("/api/v1/agent/delivery-hook")
async def secure_agent_webhook_receiver(request: Request):
    incoming_signature = request.headers.get("X-Gateway-Signature")
    if not incoming_signature:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing signature.")
    
    body_bytes = await request.body()
    
    expected_signature = hmac.new(
        WEBHOOK_SHARED_SECRET.encode('utf-8'),
        msg=body_bytes,
        digestmod=hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(incoming_signature, expected_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Signature mismatch.")
        
    return {"status": "signature_valid"}