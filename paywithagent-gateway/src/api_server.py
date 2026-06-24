import os
import json
import time
import hmac
import hashlib
from fastapi import FastAPI, HTTPException, status, Query, Request
from pydantic import BaseModel
import xrpl
from xrpl.clients import JsonRpcClient
from config import WEBHOOK_SHARED_SECRET, XRPL_NETWORK_URL
# Initialize FastAPI instance
app = FastAPI(
    title="PayWithAgent Gateway API",
    description="Machine-to-Machine commerce routing endpoints over the XRP Ledger",
    version="1.0.0"
)

xrpl_client = JsonRpcClient(XRPL_NETWORK_URL)

# Helper function to dynamically load the unified manifest data
def load_manifest():
    manifest_path = os.path.join(os.path.dirname(__file__), "ai-agent.json")
    with open(manifest_path, "r") as f:
        return json.load(f)

# Request Data Validation Schemas
class InvoiceRequest(BaseModel):
    product_id: str
    quantity: int = 1
    buyer_agent_id: str

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
    
    return {
        "status": "success",
        "invoice_id": f"INV-{int(time.time())}",
        "product_id": payload.product_id,
        "price_xrp": price_xrp,
        "price_drops": price_drops,
        "destination_address": manifest["settlement_profile"]["merchant_receiving_address"],
        "expires_in_seconds": 600
    }

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