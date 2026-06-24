
# PayWithAgent Gateway API

A compact reference for autonomous agents to discover stores, request invoices, and verify XRPL settlement.

## Endpoints

| Route | Method | Purpose |
|---|---|---|
| `/ai-agent.json` | GET | Retrieve store discovery manifest and inventory. |
| `/api/v1/agent/invoice` | POST | Create an invoice for a product purchase. |
| `/api/v1/agent/verify` | GET | Check settlement status for a transaction. |

## 1. Discovery Manifest

GET `/ai-agent.json`

Returns merchant metadata, settlement profile, and inventory.

Example response:

```json
{
  "business_metadata": {
    "legal_name": "RoastCo AI Store",
    "description": "Autonomous B2B product catalog for machine consumers."
  },
  "settlement_profile": {
    "network": "xrpl_testnet",
    "merchant_receiving_address": "rB27XmZpU6uXhS7Nn49d7H8vB1kLmNpQrs"
  },
  "inventory": [
    {
      "product_id": "PROD_001",
      "name": "Espresso Beans Bulk",
      "unit_price_xrp": 15.0
    }
  ]
}
```

## 2. Request Invoice

POST `/api/v1/agent/invoice`

Request payload:

```json
{
  "product_id": "PROD_001",
  "quantity": 1,
  "buyer_agent_id": "did:xrpl:1234567890"
}
```

Success response:

```json
{
  "status": "success",
  "invoice_id": "INV-1719183600",
  "price_xrp": 15.0,
  "price_drops": 15000000,
  "destination_address": "rB27XmZpU6uXhS7Nn49d7H8vB1kLmNpQrs",
  "expires_in_seconds": 600
}
```

Errors:
- `404` if `product_id` is invalid.
- `409` if requested quantity exceeds autonomous limits.

## 3. Verify Settlement

GET `/api/v1/agent/verify?tx_hash=<TX_HASH>&invoice_id=<INVOICE_ID>`

Settled response:

```json
{
  "status": "settled",
  "invoice_id": "INV-1719183600",
  "ledger_index": 4829105,
  "amount_received_drops": "15000000",
  "validated": true,
  "timestamp": "2026-06-24T04:20:00Z"
}
```

Pending response:

```json
{
  "status": "pending",
  "invoice_id": "INV-1719183600",
  "message": "Transaction found on ledger but awaiting structural validation confirmation."
}
```
