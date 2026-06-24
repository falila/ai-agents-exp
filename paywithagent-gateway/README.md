# 🤖 PayWithAgent Gateway

A localized, decentralized multi-agent checkout gateway that empowers small businesses to discover, negotiate, and accept autonomous payments directly from machine consumers using the XRP Ledger (XRPL), LangGraph, and Ollama.

---

## 📌 Summary

**PayWithAgent** bridges the gap between traditional retail storefronts and the burgeoning autonomous machine economy. Instead of treating automated software web scrapers as bots to be blocked, this platform serves a machine-readable commerce profile (`ai-agent.json`) that allows autonomous AI agents to browse store inventory, negotiate procurement requests via local LLMs, pass strict corporate risk guardrails, and settle transactions natively on the blockchain in under 5 seconds.

---

## 💡 Core Value Proposition

*   **For Small Businesses:** Tap into zero-friction machine-to-machine commerce workflows. Automated agents can book operational services, restock corporate inventories, or clear digital micro-purchases automatically with processing fees under a fraction of a cent.
*   **For Enterprises & Consumers:** Securely delegate mundane procurement tasks to specialized AI networks. Your internal agents can independently scout suppliers, cross-check allowances, and execute transfers without manual human clerical overhead.
*   **For the AI Ecosystem:** Provides an alternative to restrictive legacy fiat credit card portals by replacing them with high-speed, programmable blockchain settlement channels.

---

## 🚀 Key Features

### 1. Machine-Readable Commerce Manifest (`ai-agent.json`)
*   **The Feature:** Implements a standardized `/ai-agent.json` discovery schema endpoint.
*   **The Impact:** Autonomous AI crawlers can instantly scrape your storefront's product catalog, view real-time stock levels, check dynamic pricing, and locate your XRPL receiving address without needing a human web browser interface.

### 2. Local Ollama LLM Reasoning Node
*   **The Feature:** Powered by an offline `llama3` instance inside an isolated container grid.
*   **The Impact:** Processes procurement parsing logic, negotiates requests, and reads manifest metadata locally with **zero dependencies on third-party cloud API keys** (like OpenAI or Anthropic) and total merchant log data privacy.

### 3. Stateful Multi-Agent LangGraph Architecture
*   **The Feature:** Uses a deterministic, acyclic state-machine orchestration runtime to decouple agent operations.
*   **The Impact:** Splits commercial tasks among specialized, role-based nodes—a **Procurement Agent** validates item inventories, and an independent **Risk Auditor Agent** checks compliance limits before passing states forward.

### 4. Programmatic Human-in-the-Loop (HITL) Guardrails
*   **The Feature:** Integrates LangGraph's native state persistence checkpointers (`MemorySaver`) with a hard `interrupt_before` execution breakpoint.
*   **The Impact:** Completely eliminates rogue AI spending sprees. Even if the local LLM logic approves a transaction, the state is frozen safely in memory until a human merchant manually clicks a button on the UI to release the on-chain funds.

### 5. High-Velocity Cryptographic Security & Settlement
*   **The Feature:** Features native **XRPL Blockchain integration** combined with **HMAC-SHA256 Signed Webhook headers**.
*   **The Impact:** Settles machine-to-machine financial transactions globally in under 5 seconds for less than a hundredth of a cent, while protecting the agent's web endpoints from spoofing attacks via cryptographically verifiable signature handshakes.

---

## 🛠️ The Tech Stack

Our framework operates entirely local, free of cloud API lock-ins, and utilizes a decoupled stack layout:

*   **Orchestration Framework:** [LangGraph]() — Governs the cyclical multi-agent conversation memory loops and handles native state freezing.
*   **Local Inference Engine:** [Ollama](https://ollama.com) (`llama3`) — Processes structured reasoning evaluation models locally without leaking proprietary merchant logs to external servers.
*   **Settlement Engine:** [XRPL (XRP Ledger)](https://xrpl.org) (`xrpl-py`) — Dispatches near-instant, low-fee transactions via the decentralized public ledger.
*   **User Interface Portal:** [Streamlit](https://streamlit.io) — Serves a simple human analytics dashboard alongside the programmatic machine metadata tab.
*   **Dependency Engine:** [uv](https://github.com) — Blazing-fast Python package and workspace synchronization manager.

---

## 📦 Project Structure

```text
paywithagent-gateway/
├── pyproject.toml         # Unified package targets (PEP 621)
├── docker-compose.yml     # Local system container topology 
├── Dockerfile             # Multi-stage optimized app mirror
├── README.md              # Documentation portal
└── src/
    ├── app.py             # Streamlit entrypoint UI & endpoint view
    ├── ai-agent.json      # Machine-readable discovery manifest 
    ├── xrpl_client/
    │   └── wallet.py      # Automated Testnet wallet utilities
    └── agent/
        ├── state.py       # Centrally shared memory state machine
        ├── tools.py       # Settlement and invoice construction blocks
        └── graph.py       # LangGraph multi-agent flow configuration
```

---

## 🤖 Multi-Agent Logic Flow

Instead of a single linear script, the platform splits procurement logic across distinct, role-based modules:

1.  **Procurement Agent (Ollama Node):** Scrapes the store's `ai-agent.json` manifest dynamically to assess stock availability and returns structured JSON confirming a choice.
2.  **Risk Auditor Agent (Guardrail Node):** Evaluates transaction balances against a rigid corporate limit threshold policy (capped at 50 XRP).
3.  **Human-in-the-Loop Interruption:** If policies pass, LangGraph purposefully triggers an execution breakpoint (`interrupt_before`). The transaction state is serialized and paused until a human clicks an action button on the dashboard.
4.  **XRPL Settlement Engine (Execution Node):** Upon human confirmation, the loop resumes, builds the ledger payment block, signs it with the agent's private key, and broadcasts it to the XRPL Testnet.

---

## 🚀 Installation & Setup Quickstart

### Prerequisites
*   [Docker](https://docker.com) & [Docker Compose](https://docker.com) installed on your machine.
*   (Optional) [uv]() installed locally for editing environment dependencies.

### Step 1: Clone and Prepare
Move into your workspace directory containing the files:
```bash
cd paywithagent-gateway
```
*(Optional)* Generate your local dependency lock file:
```bash
uv lock
```

### Step 2: Spin Up the Infrastructure Stack
Build and launch your multi-container environment (this boots up the Streamlit interface and an independent Ollama instance concurrently):
```bash
docker compose up --build
```

### Step 3: Seed Local Model Weights
Open a new, separate terminal window while the containers are running to download the `llama3` model weights into your isolated Ollama storage volume:
```bash
docker exec -it paywithagent_ollama ollama pull llama3
```

### Step 4: Access the Dashboards
Open your browser of choice and head over to:
*   **User Interface Platform:** `http://localhost:8501`
*   **Ollama Health Check Server:** `http://localhost:11434`

---

## ⚙️ Configuration Parameters

The gateway parameters can be modified directly within the configuration files:

*   **Inventory & Pricing Modifications:** Edit `src/ai-agent.json` to alter item names, product IDs, and unit prices.
*   **Network Targets:** The `docker-compose.yml` file defaults environment routes to the public Testnet endpoint (`https://rippletest.net`). Swap this to an alternative Mainnet node or local rippled server as needed.
*   **Audit Ceiling Rules:** To adjust spending thresholds, modify the `MAX_ALLOWANCE_XRP` condition in `src/agent/graph.py` (currently set to `50.0` XRP).

---

# API Reference

A compact reference for autonomous agents to discover stores, request invoices, and verify XRPL settlement.

## Endpoints

| Route | Method | Purpose |
|---|---|---|
| `/ai-agent.json` | GET | Retrieve store discovery manifest and inventory. |
| `/api/v1/agent/invoice` | POST | Create an invoice for a product purchase. |
| `/api/v1/agent/verify` | GET | Check whether an XRPL payment has been settled. |

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
