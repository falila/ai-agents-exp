import streamlit as st
import io
import json
import os
import uuid
from config import XRPL_NETWORK_URL, MERCHANT_RECEIVING_ADDRESS, MERCHANT_WALLET_ADDRESS
from xrpl_client.wallet import XRPLManager
from agent.graph import compiled_agent_graph
from db import initialize_history_db, fetch_transaction_history, record_settlement_history
from utils import load_manifest, get_state_field, maybe_rerun

NODE_URL = XRPL_NETWORK_URL
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

initialize_history_db()

if "history_rows" not in st.session_state:
    st.session_state.history_rows = fetch_transaction_history()

xrpl_mgr = XRPLManager(NODE_URL)
manifest_data = load_manifest()

configured_merchant_address = MERCHANT_WALLET_ADDRESS or MERCHANT_RECEIVING_ADDRESS or manifest_data["settlement_profile"].get("merchant_receiving_address")

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
        "merchant_address": merchant_address,
    }
} if wallets_ready else None

with st.sidebar:
    agent_wallet_address = st.session_state.agent_wallet.address if st.session_state.agent_wallet is not None else "Unavailable"
    merchant_display = merchant_address or "Not configured"
    webhook_url = manifest_data.get("agent_endpoints", {}).get("webhook_delivery_notification_url")
    webhook_status = "Active" if webhook_url else "Not configured"
    webhook_badge = "#10b981" if webhook_url else "#f59e0b"
    status_text = "Completed" if st.session_state.release_complete else "Pending release" if st.session_state.release_events else "Idle"

    st.markdown(
        "<div style='padding: 18px; border-radius: 22px; background: linear-gradient(135deg, #0f172a, #1e293b); color: #f8fafc; box-shadow: 0 18px 40px rgba(15, 23, 42, 0.22);'>"
        "<div style='font-size:20px; font-weight:700; margin-bottom:6px;'>Merchant Dashboard</div>"
        "<div style='font-size:13px; color:#cbd5e1; line-height:1.6;'>A merchant-facing control panel for payment settlement, agent identity, and webhook status.</div>"
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

    st.markdown("<div style='margin-top:16px; padding:16px; border-radius:18px; background:#111827; color:#f8fafc; border:1px solid rgba(148, 163, 184, 0.18);'>"
                "<div style='font-size:14px; font-weight:700; margin-bottom:10px;'>Webhook Status</div>"
                "<div style='display:flex; align-items:center; gap:8px; margin-bottom:10px;'>"
                f"<span style='width:10px; height:10px; border-radius:999px; display:inline-block; background:{webhook_badge};'></span>"
                f"<span style='font-size:12px; color:#e2e8f0;'>{webhook_status}</span>"
                "</div>"
                "<div style='font-size:11px; color:#94a3b8; margin-bottom:8px;'>Delivery endpoint</div>"
                f"<div style='font-size:12px; line-height:1.5; word-break:break-all; color:#e2e8f0;'>{webhook_url or 'Not available'}</div>"
                "<div style='margin-top:12px; font-size:12px; color:#c7d2fe;'>Auth: HMAC-SHA256</div>"
                "</div>", unsafe_allow_html=True)

    st.markdown("<div style='margin-top:16px; padding:16px; border-radius:18px; background:#0f172a; color:#f8fafc; border:1px solid rgba(148, 163, 184, 0.18);'>"
                "<div style='font-size:14px; font-weight:700; margin-bottom:10px;'>Runtime Snapshot</div>"
                f"<div style='font-size:12px; color:#94a3b8; margin-bottom:6px;'>Release state</div><div style='font-size:13px; color:#e2e8f0;'>{status_text}</div>"
                "</div>", unsafe_allow_html=True)

    st.markdown("---")
    st.caption("Merchant control and settlement health details.")

st.title("🛍️ Merchant Dashboard")
st.markdown(
    "A dedicated merchant dashboard for monitoring transaction history, agent progress, and your published `ai-agent.json` manifest."
)

tab1, tab2, tab3 = st.tabs(["Storefront UI", "Merchant History", "AI Manifest JSON Endpoint"])

with tab1:
    st.header("Storefront Control")
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
                        if event.get("result") and isinstance(event.get("result", dict)):
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

def _api_get_json(url: str):
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        st.error(f"Failed to fetch from merchant API: {exc}")
        return None


def _api_post_json(url: str, body: dict):
    import urllib.request
    import urllib.error
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            payload = json.loads(exc.read().decode("utf-8"))
            detail = payload.get("detail")
        except Exception:
            detail = ""
        if detail:
            st.error(f"Merchant release request failed ({exc.code}): {detail}")
        else:
            st.error(f"Merchant release request failed: {exc}")
        return None
    except Exception as exc:
        st.error(f"Merchant release request failed: {exc}")
        return None

with tab2:
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

with tab3:
    st.json(manifest_data)

with st.expander("Pending consumer orders"):
    st.caption(f"Orders API: {API_BASE_URL}")
    pending_orders = _api_get_json(f"{API_BASE_URL}/api/v1/agent/orders")
    if pending_orders is None:
        st.warning("Could not reach merchant API. Check API_BASE_URL and API service status.")
    elif not pending_orders:
        st.info("No pending orders currently awaiting merchant release.")
    else:
        for order in pending_orders:
            st.markdown(f"### Order {order['invoice_id']}")
            st.json(order)
            if order["status"] != "SETTLED":
                if st.button(f"Release funds for {order['invoice_id']}", key=order['invoice_id']):
                    release_result = _api_post_json(f"{API_BASE_URL}/api/v1/agent/release/{order['invoice_id']}", {})
                    if release_result:
                        st.success(f"Order {order['invoice_id']} released.")
                        st.write(release_result)
