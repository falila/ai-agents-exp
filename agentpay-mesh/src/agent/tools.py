import time
from xrpl.models.transactions import Payment
from xrpl.models.requests import SubmitOnly
from xrpl.transaction import autofill_and_sign, submit_and_wait
from xrpl.wallet import Wallet
from config import WEBHOOK_SHARED_SECRET
import urllib.request
import json
import hmac
import hashlib


def generate_invoice(product_id: str, price_xrp: float) -> dict:
    return {"invoice_id": f"INV-{int(time.time())}", "price": price_xrp}

def settle_xrpl_invoice(client, agent_wallet, merchant_address, amount_drops):
    tx = Payment(
        account=agent_wallet.address,
        amount=str(int(amount_drops)),
        destination=merchant_address
    )
    signed = autofill_and_sign(tx, client, agent_wallet)
    response = submit_and_wait(signed, client)
    return response.result["hash"]


def build_presigned_consumer_payment_payload(
    client,
    consumer_wallet_secret: str,
    consumer_wallet_address: str,
    destination_address: str,
    amount_drops: int,
) -> dict:
    if not consumer_wallet_secret:
        raise ValueError("CONSUMER_WALLET_SECRET is not configured.")
    if not destination_address:
        raise ValueError("Merchant destination address is missing in ai-agent.json.")

    wallet = Wallet.from_seed(consumer_wallet_secret)
    if consumer_wallet_address and wallet.address != consumer_wallet_address:
        raise ValueError("CONSUMER_WALLET_ADDRESS does not match CONSUMER_WALLET_SECRET.")
    if wallet.address == destination_address:
        raise ValueError("Consumer wallet address cannot be the same as the merchant destination address.")

    tx = Payment(
        account=wallet.address,
        destination=destination_address,
        amount=str(int(amount_drops)),
    )
    signed = autofill_and_sign(tx, client, wallet)

    blob_candidate = getattr(signed, "blob", None)
    if callable(blob_candidate):
        blob_candidate = blob_candidate()

    tx_blob_candidate = getattr(signed, "tx_blob", None)
    if callable(tx_blob_candidate):
        tx_blob_candidate = tx_blob_candidate()

    signed_blob = blob_candidate or tx_blob_candidate
    if isinstance(signed_blob, bytes):
        signed_blob = signed_blob.decode("utf-8")
    if not signed_blob:
        raise ValueError("Could not build signed XRPL transaction blob.")

    return {
        "signed_tx_blob": signed_blob,
        "account": wallet.address,
        "destination": destination_address,
        "amount_drops": int(amount_drops),
    }


def settle_consumer_payment_payload(client, payment_payload: dict, expected_merchant_address: str, expected_amount_drops: int) -> str:
    """Submit a consumer-provided XRPL payload and return the resulting tx hash.

    Supported payload format:
    - {"signed_tx_blob": "..."}
    """
    signed_blob = (payment_payload or {}).get("signed_tx_blob")
    if not signed_blob:
        raise ValueError("Missing signed_tx_blob in payment_payload.")

    payload_destination = (payment_payload or {}).get("destination")
    if payload_destination and expected_merchant_address and payload_destination != expected_merchant_address:
        raise ValueError("Payment payload destination does not match merchant destination address.")

    payload_amount_drops = (payment_payload or {}).get("amount_drops")
    if payload_amount_drops is not None and int(payload_amount_drops) != int(expected_amount_drops):
        raise ValueError("Payment payload amount does not match expected invoice amount.")

    response = client.request(SubmitOnly(tx_blob=signed_blob))
    result = response.result or {}
    engine_result = result.get("engine_result")
    if engine_result != "tesSUCCESS":
        engine_message = result.get("engine_result_message") or ""
        raise RuntimeError(f"XRPL submission failed with engine result: {engine_result} {engine_message}".strip())

    tx_hash = (result.get("tx_json") or {}).get("hash")
    if not tx_hash:
        raise RuntimeError("XRPL submission succeeded but no transaction hash was returned.")
    return tx_hash



def trigger_agent_delivery_webhook(
    target_url: str, 
    invoice_id: str, 
    tx_hash: str, 
    product_id: str,
    max_retries: int = 3,
    initial_delay: float = 2.0
):
    """
    Dispatches an HMAC-signed webhook to the consumer agent.
    Implements exponential backoff retry loops for handling connection drops.
    """
    payload = {
        "event": "transaction.released",
        "timestamp": int(time.time()),
        "data": {
            "invoice_id": invoice_id,
            "xrpl_tx_hash": tx_hash,
            "product_id": product_id,
            "status": "SETTLED"
        }
    }
    
    req_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    
    signature = hmac.new(
        WEBHOOK_SHARED_SECRET.encode('utf-8'),
        msg=req_bytes,
        digestmod=hashlib.sha256
    ).hexdigest()
    
    current_delay = initial_delay

    for attempt in range(1, max_retries + 1):
        req = urllib.request.Request(
            target_url, 
            data=req_bytes, 
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'PayWithAgent-Gateway/1.0',
                'X-Gateway-Signature': signature
            }
        )
        
        try:
            print(f"[Webhook Node]: Attempt {attempt} of {max_retries} to {target_url}...")
            # Low timeout per attempt to keep the state machine moving
            with urllib.request.urlopen(req, timeout=3) as response:
                if response.getcode() in [200, 201, 202]:
                    return {
                        "status": "success",
                        "attempts": attempt,
                        "http_code": response.getcode()
                    }
        except Exception as e:
            print(f"[Webhook Warning]: Attempt {attempt} failed due to: {str(e)}")
            
        # If this wasn't our final attempt, wait before trying again
        if attempt < max_retries:
            print(f"[Webhook Retry Loop]: Sleeping for {current_delay}s before re-trying...")
            time.sleep(current_delay)
            current_delay *= 2  # Exponentially double the delay window

    return {
        "status": "failed",
        "attempts": max_retries,
        "message": "Max retry limit reached. Target agent node remains unreachable."
    }
    


