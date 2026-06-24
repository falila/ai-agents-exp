import streamlit as st
import json
import io
import os
import sqlite3
import uuid
from datetime import datetime
from config import XRPL_NETWORK_URL, MERCHANT_RECEIVING_ADDRESS
from xrpl_client.wallet import XRPLManager
from agent.graph import compiled_agent_graph

NODE_URL = XRPL_NETWORK_URL
DB_PATH = os.path.join(os.path.dirname(__file__), "merchant_history.db")


def initialize_history_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS merchant_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            thread_id TEXT,
            invoice_id TEXT,
            product_id TEXT,
            price_drops INTEGER,
            amount_xrp REAL,
            merchant_address TEXT,
            tx_hash TEXT,
            status TEXT,
            webhook_url TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def record_transaction(entry):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO merchant_transactions (
            created_at, thread_id, invoice_id, product_id, price_drops, amount_xrp,
            merchant_address, tx_hash, status, webhook_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entry["created_at"],
            entry["thread_id"],
            entry["invoice_id"],
            entry["product_id"],
            entry["price_drops"],
            entry["amount_xrp"],
            entry["merchant_address"],
            entry["tx_hash"],
            entry["status"],
            entry["webhook_url"],
        ),
    )
    conn.commit()
    conn.close()


def fetch_transaction_history():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT created_at, thread_id, invoice_id, product_id, price_drops, amount_xrp, merchant_address, tx_hash, status, webhook_url"
        " FROM merchant_transactions ORDER BY id DESC"
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def record_settlement_history(frozen, tx_hash, webhook_url, thread_id, merchant_address):
    if not frozen:
        return
    entry = {
        "created_at": datetime.utcnow().isoformat() + "Z",
        "thread_id": thread_id,
        "invoice_id": frozen.get("invoice_id"),
        "product_id": frozen.get("target_product_id"),
        "price_drops": frozen.get("price_drops"),
        "amount_xrp": (frozen.get("price_drops", 0) or 0) / 1_000_000,
        "merchant_address": merchant_address,
        "tx_hash": tx_hash or "",
        "status": "SETTLED" if tx_hash else "RELEASED",
        "webhook_url": webhook_url or "",
    }
    record_transaction(entry)
    st.session_state.history_rows = fetch_transaction_history()

initialize_history_db()

if "history_rows" not in st.session_state:
    st.session_state.history_rows = fetch_transaction_history()

xrpl_mgr = XRPLManager(NODE_URL)

MANIFEST_PATH = os.path.join(os.path.dirname(__file__), "ai-agent.json")
with open(MANIFEST_PATH, "r") as f:
    manifest_data = json.load(f)

configured_merchant_address = MERCHANT_RECEIVING_ADDRESS or manifest_data["settlement_profile"].get("merchant_receiving_address")

if "merchant_wallet" not in st.session_state:
    with st.spinner("Generating Testnet identities..."):
        try:
            st.session_state.agent_wallet = xrpl_mgr.create_testnet_wallet()
            if configured_merchant_address:
                st.session_state.merchant_wallet = None
            else:
                st.session_state.merchant_wallet = xrpl_mgr.create_testnet_wallet()
        except Exception:
            st.warning("Unable to generate testnet wallets at startup. Please check network access.")
            st.session_state.merchant_wallet = None
            st.session_state.agent_wallet = None
        st.session_state.current_thread_id = str(uuid.uuid4())
        st.session_state.release_events = []
        st.session_state.release_thread_id = None
        st.session_state.release_complete = False

merchant_address = configured_merchant_address
if st.session_state.merchant_wallet is not None:
    merchant_address = st.session_state.merchant_wallet.address

if merchant_address:
    manifest_data["settlement_profile"]["merchant_receiving_address"] = merchant_address
    if configured_merchant_address:
        st.info("Using configured merchant receiving address from MERCHANT_RECEIVING_ADDRESS.")
else:
    st.error("Merchant receiving address is not configured.")

wallets_ready = st.session_state.agent_wallet is not None and merchant_address is not None
run_config = {
    "configurable": {
        "thread_id": st.session_state.current_thread_id,
        "xrpl_client": xrpl_mgr.client,
        "agent_wallet": st.session_state.agent_wallet,
        "merchant_address": merchant_address
    }
} if wallets_ready else None

if "current_progress_stage" not in st.session_state:
    st.session_state.current_progress_stage = None


def get_state_field(state, field):
    if state is None:
        return None
    if not hasattr(state, field):
        return None
    value = getattr(state, field)
    if callable(value):
        try:
            return value()
        except TypeError:
            return value
    return value


def normalize_state_key(value):
    if value is None:
        return None
    if isinstance(value, (list, tuple)) and len(value) > 0:
        return normalize_state_key(value[0])
    if isinstance(value, dict):
        return normalize_state_key(value.get("name") or value.get("id"))
    if isinstance(value, str):
        return value
    return None


def maybe_rerun():
    rerun = getattr(st, "experimental_rerun", None)
    if callable(rerun):
        try:
            rerun()
        except Exception:
            pass

with st.sidebar:
    agent_wallet_address = st.session_state.agent_wallet.address if st.session_state.agent_wallet is not None else "Unavailable"
    merchant_display = merchant_address or "Not configured"
    webhook_url = manifest_data.get("agent_endpoints", {}).get("webhook_delivery_notification_url")
    webhook_status = "Active" if webhook_url else "Not configured"
    webhook_badge = "#10b981" if webhook_url else "#f59e0b"
    status_text = "Completed" if st.session_state.release_complete else "Pending release" if st.session_state.release_events else "Idle"
    progress_stage = st.session_state.current_progress_stage or "Waiting"

    st.markdown(
        "<div style='padding: 18px; border-radius: 22px; background: linear-gradient(135deg, #0f172a, #1e293b); color: #f8fafc; box-shadow: 0 18px 40px rgba(15, 23, 42, 0.22);'>"
        "<div style='font-size:20px; font-weight:700; margin-bottom:6px;'>Agent Gateway</div>"
        "<div style='font-size:13px; color:#cbd5e1; line-height:1.6;'>A concise runtime panel for agent identity, merchant settlement, and webhook delivery status.</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<div style='margin-top:18px; padding:16px; border-radius:18px; background:#0f172a; color:#f8fafc; border:1px solid rgba(148, 163, 184, 0.16);'>"
                "<div style='font-size:14px; font-weight:700; margin-bottom:10px;'>Agent ID Card</div>"
                f"<div style='font-size:11px; color:#94a3b8; margin-bottom:8px;'>Wallet address</div><div style='font-size:12px; line-height:1.5; word-break:break-all; color:#e2e8f0;'>{agent_wallet_address}</div>"
                f"<div style='margin-top:12px; font-size:11px; color:#94a3b8;'>Thread ID</div><div style='font-size:12px; color:#e2e8f0;'>{st.session_state.current_thread_id}</div>"
                "</div>", unsafe_allow_html=True)

    st.markdown("<div style='margin-top:16px; padding:16px; border-radius:18px; background:#111827; color:#f8fafc; border:1px solid rgba(148, 163, 184, 0.18);'>"
                "<div style='font-size:14px; font-weight:700; margin-bottom:10px;'>Merchant Settlement</div>"
                "<div style='font-size:11px; color:#94a3b8; margin-bottom:8px;'>Receiving address</div>"
                f"<div style='font-size:12px; line-height:1.5; word-break:break-all; color:#e2e8f0;'>{merchant_display}</div>"
                f"<div style='margin-top:12px; font-size:12px; color:#c7d2fe;'>Source: {'Configured' if configured_merchant_address else 'Generated'}</div>"
                "</div>", unsafe_allow_html=True)

    webhook_card = (
        f"<div style='margin-top:16px; padding:16px; border-radius:18px; background:#111827; color:#f8fafc; border:1px solid rgba(148, 163, 184, 0.18);'>"
        f"<div style='font-size:14px; font-weight:700; margin-bottom:10px;'>Webhook Status</div>"
        f"<div style='display:flex; align-items:center; gap:8px; margin-bottom:10px;'>"
        f"<span style='width:10px; height:10px; border-radius:999px; display:inline-block; background:{webhook_badge};'></span>"
        f"<span style='font-size:12px; color:#e2e8f0;'>{webhook_status}</span>"
        "</div>"
        f"<div style='font-size:11px; color:#94a3b8; margin-bottom:8px;'>Delivery endpoint</div>"
        f"<div style='font-size:12px; line-height:1.5; word-break:break-all; color:#e2e8f0;'>{webhook_url or 'Not available'}</div>"
        f"<div style='margin-top:12px; font-size:12px; color:#c7d2fe;'>Auth: HMAC-SHA256</div>"
        "</div>"
    )
    st.markdown(webhook_card, unsafe_allow_html=True)

    st.markdown("<div style='margin-top:16px; padding:16px; border-radius:18px; background:#0f172a; color:#f8fafc; border:1px solid rgba(148, 163, 184, 0.18);'>"
                "<div style='font-size:14px; font-weight:700; margin-bottom:10px;'>Runtime Snapshot</div>"
                f"<div style='font-size:12px; color:#94a3b8; margin-bottom:6px;'>Release state</div><div style='font-size:13px; color:#e2e8f0;'>{status_text}</div>"
                f"<div style='margin-top:10px; font-size:12px; color:#94a3b8; margin-bottom:6px;'>Current progress stage</div><div style='font-size:13px; color:#e2e8f0;'>{progress_stage}</div>"
                "</div>", unsafe_allow_html=True)

    st.markdown("---")
    st.caption("A refined sidebar for identity, merchant settlement, and webhook health details.")

tab1, tab2, tab3, tab4 = st.tabs(["Storefront UI", "Progress", "Merchant History", "AI Manifest JSON Endpoint"])

with tab2:
    st.subheader("🚦 Multi-Agent Cycle")
    st.markdown("A clean overview of the current multi-agent workflow, with the active stage highlighted and pending steps shown below.")

    steps = [
        {"id": "procurement", "label": "Procurement Review", "description": "Validate product and generate invoice."},
        {"id": "risk_auditor", "label": "Risk Auditor", "description": "Check spending limits and approve request."},
        {"id": "settlement_engine", "label": "Settlement Engine", "description": "Execute on-chain payment and notify webhook."}
    ]

    if not wallets_ready or run_config is None:
        st.warning("Wallets or merchant configuration are not ready yet. Run the storefront cycle first to initialize the multi-agent workflow.")
    else:
        current_state = compiled_agent_graph.get_state(run_config)
        active = normalize_state_key(get_state_field(current_state, "next") or get_state_field(current_state, "name"))
        if active is None and st.session_state.release_complete:
            active = "complete"
        st.session_state.current_progress_stage = active

        step_order = [step["id"] for step in steps]
        active_index = step_order.index(active) if active in step_order else -1
        progress_value = 100 if active == "complete" else int(((active_index + 1) / len(step_order)) * 100) if active_index >= 0 else 0

        st.metric("Cycle status", "Complete" if active == "complete" else "In progress" if active_index >= 0 else "Idle")
        st.progress(progress_value)

        st.markdown("---")
        for index, step in enumerate(steps):
            if active == step["id"]:
                status = "Current"
                icon = "➡️"
                style = "background-color: #fff3bf; color: #000; padding: 16px; border-radius: 14px; border: 1px solid #d4d4d4; margin-bottom: 10px;"
            elif active == "complete" or index < active_index:
                status = "Completed"
                icon = "✅"
                style = "background-color: #d1e7dd; color: #000; padding: 16px; border-radius: 14px; border: 1px solid #c1d4c1; margin-bottom: 10px;"
            else:
                status = "Pending"
                icon = "⏳"
                style = "background-color: #f8f9fa; color: #000; padding: 16px; border-radius: 14px; border: 1px solid #c6c8ca; margin-bottom: 10px;"

            st.markdown(
                f"<div style='{style}'>"
                f"<div style=\"font-size:16px; font-weight:700; margin-bottom:6px;\">{icon} {step['label']}</div>"
                f"<div style=\"color:#444; margin-bottom:10px;\">{step['description']}</div>"
                f"<div style=\"font-size:14px; font-weight:600; color:#333;\">Status: {status}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        pending_steps = [step["label"] for i, step in enumerate(steps) if i > active_index and active != "complete"]
        if pending_steps:
            st.markdown("**Pending next steps:**")
            for label in pending_steps:
                st.markdown(f"- {label}")
        elif active == "complete":
            st.success("All multi-agent workflow steps are complete.")
        else:
            st.info("The cycle has not yet begun or is waiting for the first input.")

with tab3:
    st.markdown("<div style='padding:24px; border-radius:24px; background:#f8fafc; color:#0f172a;'>"
                "<div style='font-size:22px; font-weight:700; margin-bottom:10px;'>Merchant Transaction History</div>"
                "<div style='font-size:14px; color:#475569; margin-bottom:16px;'>A record of completed merchant settlements with invoice, amount, and transaction IDs.</div>"
                "</div>", unsafe_allow_html=True)
    history_rows = st.session_state.get("history_rows", fetch_transaction_history())
    if not history_rows:
        history_rows = fetch_transaction_history()
        st.session_state.history_rows = history_rows
    if history_rows:
        history_records = [
            {
                "Timestamp": row[0],
                "Thread": row[1],
                "Invoice": row[2],
                "Product": row[3],
                "Amount (XRP)": row[5],
                "Merchant": row[6],
                "TX Hash": row[7],
                "Status": row[8],
                "Webhook": row[9],
            }
            for row in history_rows
        ]

        csv_buffer = io.StringIO()
        csv_header = ",".join(history_records[0].keys())
        csv_buffer.write(csv_header + "\n")
        for record in history_records:
            csv_buffer.write(",".join([str(record[key]).replace(",", " ") for key in record.keys()]) + "\n")
        csv_data = csv_buffer.getvalue()

        json_data = json.dumps(history_records, indent=2)

        st.markdown("<div style='display:flex; gap:12px; margin-bottom:16px;'>", unsafe_allow_html=True)
        st.download_button("Download CSV", csv_data, file_name="merchant_history.csv", mime="text/csv")
        st.download_button("Download JSON", json_data, file_name="merchant_history.json", mime="application/json")
        st.markdown("</div>", unsafe_allow_html=True)

        st.table(history_records)
    else:
        st.info("No completed merchant transactions have been recorded yet.")

with tab4:
    st.json(manifest_data)

with tab1:
    st.title("🛡️ Human-in-the-Loop Agent Gateway")
    product_options = {p["product_id"]: p["name"] for p in manifest_data["inventory"]}
    target_product = st.selectbox("Select Target Product", options=list(product_options.keys()), format_func=lambda x: product_options[x])

    if not wallets_ready:
        st.error("Cannot run the multi-agent gateway because the agent wallet or merchant receiving address is unavailable. Check XRPL network access and configuration.")
        st.stop()

    if st.button("Run Multi-Agent Cycle"):
        st.session_state.release_events = []
        st.session_state.release_complete = False
        initial_state = {"target_product_id": target_product, "inventory_metadata": manifest_data}
        for event in compiled_agent_graph.stream(initial_state, run_config):
            st.json(event)
        maybe_rerun()

    if not st.session_state.release_complete:
        current_state = compiled_agent_graph.get_state(run_config)
        active = get_state_field(current_state, "next") or get_state_field(current_state, "name")
        if active:
            frozen = current_state.values
            st.warning(f"⚠️ **PAUSED BY HUMAN-IN-THE-LOOP:** Requesting {frozen.get('price_drops')/1_000_000} XRP for Invoice `{frozen.get('invoice_id')}`")
            if st.button("✅ Release On-Chain Funds", type="primary"):
                st.session_state.release_thread_id = st.session_state.current_thread_id
                st.session_state.release_events = []
                for next_event in compiled_agent_graph.stream(None, run_config):
                    st.session_state.release_events.append(next_event)

                tx_hash = None
                for event in st.session_state.release_events:
                    if isinstance(event, dict):
                        if event.get("xrpl_tx_hash"):
                            tx_hash = event.get("xrpl_tx_hash")
                            break
                        if event.get("result") and isinstance(event.get("result"), dict):
                            tx_hash = event["result"].get("xrpl_tx_hash") or tx_hash

                record_settlement_history(
                    frozen=frozen,
                    tx_hash=tx_hash,
                    webhook_url=manifest_data.get("agent_endpoints", {}).get("webhook_delivery_notification_url"),
                    thread_id=st.session_state.release_thread_id,
                    merchant_address=merchant_address,
                )

                st.session_state.release_complete = True
                st.session_state.current_thread_id = str(uuid.uuid4())
                maybe_rerun()

    if st.session_state.release_events:
        st.success("Release completed. Review the next events below.")
        for event in st.session_state.release_events:
            st.json(event)
        if st.button("Start new multi-agent cycle"):
            st.session_state.release_events = []
            st.session_state.release_complete = False
            st.session_state.current_thread_id = str(uuid.uuid4())
