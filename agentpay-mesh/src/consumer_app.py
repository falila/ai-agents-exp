import os
import streamlit as st
import uuid
from agent.runner import chat_search, confirm_purchase, get_order_status

try:
    from streamlit import st_autorefresh
except ImportError:
    st_autorefresh = None

if "consumer_chat_history" not in st.session_state:
    st.session_state.consumer_chat_history = []

if "search_results" not in st.session_state:
    st.session_state.search_results = []

if "purchase_preview" not in st.session_state:
    st.session_state.purchase_preview = None

st.title("🛒 Consumer Agent Dashboard")
st.markdown(
    "A dedicated consumer-facing dashboard for autonomous product discovery and checkout. "
    "Enter a product description, and confirm the purchase to initiate a machine-to-machine transaction with the merchant agent."
)

default_manifest_url = os.getenv("MERCHANT_MANIFEST_URL", "http://localhost:8000/ai-agent.json")
merchant_manifest_url = default_manifest_url

user_query = st.text_input("What are you looking for?", key="chat_query")
if st.button("Search Products"):
    if user_query:
        try:
            search_response = chat_search(user_query, merchant_manifest_url=merchant_manifest_url)
            st.session_state.search_results = [search_response["match"]] if search_response.get("match") else []
            st.session_state.consumer_chat_history.append({"type": "user", "message": user_query})
            found_message = (
                f"Matched product: {search_response['match']['name']} ({search_response['match']['product_id']})"
                if search_response.get("match")
                else "No close match found for your query."
            )
            st.session_state.consumer_chat_history.append({"type": "system", "message": found_message})
        except Exception as exc:
            st.error(f"Search failed: {exc}")
    else:
        st.warning("Please enter a product name or description to search.")

if st.session_state.search_results:
    st.markdown("### Closest matched product")
    item = st.session_state.search_results[0]
    st.markdown(
        "**{}**  \nSKU: `{}`  \nID: `{}`  \nPrice: **{} XRP**  \n{}".format(
            item["name"],
            item["sku"],
            item["product_id"],
            item["unit_price_xrp"],
            item.get("description", ""),
        )
    )
    if item.get("reasoning"):
        st.info(f"LLM reasoning: {item['reasoning']}")

    selection_id = item["product_id"]
    quantity = st.number_input(
        "Quantity",
        min_value=1,
        max_value=item.get("max_autonomous_order_qty", 1),
        value=1,
    )
    shipping_address = st.text_area(
        "Shipping address",
        value="123 Main St, City, Country",
        help="A shipping address is required for most inventory items.",
    )

    if st.button("Confirm Purchase"):
        try:
            buyer_agent_id = f"consumer-agent-{uuid.uuid4().hex[:8]}"
            shipping_data = {"address_line": shipping_address}
            with st.spinner("Waiting for procurement and risk auditor response..."):
                purchase_response = confirm_purchase(
                    selection_id=selection_id,
                    quantity=quantity,
                    shipping_address=shipping_data,
                    buyer_agent_id=buyer_agent_id,
                    merchant_manifest_url=merchant_manifest_url,
                )
            st.session_state.purchase_preview = purchase_response
            if purchase_response.get("invoice_id"):
                try:
                    st.session_state.purchase_preview["order_status"] = get_order_status(
                        purchase_response["invoice_id"],
                        merchant_manifest_url=merchant_manifest_url,
                    )
                except Exception:
                    pass
            st.session_state.consumer_chat_history.append({"type": "user", "message": f"Confirm purchase {quantity} x {selection_id}."})
            st.success("Purchase order created. Waiting on merchant release.")
        except Exception as exc:
            st.error(f"Purchase failed: {exc}")

if st.session_state.purchase_preview:
    st.markdown("### Purchase preview")
    st.write(st.session_state.purchase_preview)

    invoice_id = st.session_state.purchase_preview.get("invoice_id")
    if invoice_id:
        st.markdown(f"**Invoice ID:** `{invoice_id}`")

        order_status = st.session_state.purchase_preview.get("order_status") or {}
        if order_status:
            status_value = order_status.get("status", "UNKNOWN")
            badge_color = "#f59e0b" if status_value not in ["SETTLED", "settled"] else "#10b981"
            badge_label = "Awaiting merchant release" if status_value not in ["SETTLED", "settled"] else "Settled"
            st.markdown(
                f"<div style='display:inline-flex; align-items:center; gap:8px; padding:12px 16px; border-radius:999px; background:{badge_color}; color:#ffffff; font-weight:700;'>"
                f"<span>{badge_label}</span>"
                f"</div>", unsafe_allow_html=True,
            )

        if st.button("Refresh order status"):
            try:
                status_response = get_order_status(invoice_id, merchant_manifest_url=merchant_manifest_url)
                st.session_state.purchase_preview["order_status"] = status_response
            except Exception as exc:
                st.error(f"Order status check failed: {exc}")

        if st_autorefresh is not None and st.session_state.purchase_preview.get("order_status"):
            order_status = st.session_state.purchase_preview["order_status"]
            if order_status.get("status") != "SETTLED":
                st_autorefresh(interval=5000, limit=12, key="order_poll")
                try:
                    refreshed = get_order_status(invoice_id, merchant_manifest_url=merchant_manifest_url)
                    st.session_state.purchase_preview["order_status"] = refreshed
                except Exception:
                    pass

        if st.session_state.purchase_preview.get("order_status"):
            st.markdown("### Order status")
            st.json(st.session_state.purchase_preview["order_status"])

            if st.session_state.purchase_preview["order_status"].get("status") == "SETTLED":
                st.success("🎉 Payment settled. Merchant has released funds.")

st.markdown("### Conversation history")
for message in st.session_state.consumer_chat_history:
    if message["type"] == "user":
        st.markdown(f"**You:** {message['message']}")
    else:
        st.markdown(f"**System:** {message['message']}")
