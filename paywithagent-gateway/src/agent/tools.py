import time
from xrpl.models.transactions import Payment
from xrpl.transaction import autofill_and_sign, submit_and_wait
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
    


