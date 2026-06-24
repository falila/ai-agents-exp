import json
import os
import time
from typing import Literal, Dict, Any
from langchain_ollama import ChatOllama
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from xrpl_client.state import AgentCommerceState
from agent.tools import generate_invoice, settle_xrpl_invoice, trigger_agent_delivery_webhook
from config import OLLAMA_BASE_URL, LLM_MODEL_NAME, MAX_ALLOWANCE_XRP


llm = ChatOllama(model=LLM_MODEL_NAME, temperature=0, base_url=OLLAMA_BASE_URL)


def procurement_agent_node(state: AgentCommerceState) -> Dict[str, Any]:
    prod_id = state["target_product_id"]
    manifest = state["inventory_metadata"]
    inventory_list = manifest.get("inventory", [])
    
    sys_prompt = (
        "You are a procurement engine. Evaluate the inventory and decide if the product ID is valid.\n"
        "Respond ONLY with a valid raw JSON object matching this schema:\n"
        "{\"decision\": \"PROCEED\" or \"ABORT\", \"reasoning\": \"text\"}"
    )
    user_prompt = f"Target ID: {prod_id}\nManifest: {json.dumps(manifest)}"
    
    try:
        response = llm.invoke([("system", sys_prompt), ("human", user_prompt)])
        # Clean potential markdown wrapping from local models
        clean_content = response.content.strip().replace("```json", "").replace("```", "")
        llm_data = json.loads(clean_content)
        
        if llm_data.get("decision") == "ABORT":
            return {"procurement_decision": "ABORT", "rejection_reason": llm_data.get("reasoning")}
            
        target_item = next((item for item in inventory_list if item["product_id"] == prod_id), None)
        invoice_res = generate_invoice(prod_id, target_item["unit_price_xrp"])
        
        return {
            "procurement_decision": "PROCEED",
            "invoice_id": invoice_res["invoice_id"],
            "price_drops": int(invoice_res["price"] * 1_000_000)
        }
    except Exception as e:
        return {"procurement_decision": "ABORT", "rejection_reason": str(e)}

def risk_auditor_agent_node(state: AgentCommerceState) -> dict:
    price_xrp = state.get("price_drops", 0) / 1_000_000
    
    # Evaluate against dynamic dynamic configurations
    if price_xrp > MAX_ALLOWANCE_XRP:
        return {"auditor_approved": False, "rejection_reason": f"Breached ceiling of {MAX_ALLOWANCE_XRP} XRP"}
    return {"auditor_approved": True}


def xrpl_settlement_node(state: AgentCommerceState, config: RunnableConfig | None = None) -> Dict[str, Any]:
    """Autonomously executes the XRPL transaction and notifies the agent via a webhook."""
    if config is None:
        raise ValueError("XRPL settlement node requires a RunnableConfig with configurable runtime settings.")
    client = config["configurable"]["xrpl_client"]
    agent_wallet = config["configurable"]["agent_wallet"]
    merchant_address = config["configurable"]["merchant_address"]
    manifest = state["inventory_metadata"]
    
    print("[Settlement Engine]: Processing on-chain payment structure via XRPL...")
    
    # 1. Execute the on-chain transaction
    tx_hash = settle_xrpl_invoice(
        client=client,
        agent_wallet=agent_wallet,
        merchant_address=merchant_address,
        amount_drops=state["price_drops"]
    )
    
    # 2. Extract the agent notification endpoint from the manifest schema
    agent_endpoints = manifest.get("agent_endpoints", {})
    webhook_target = agent_endpoints.get(
        "webhook_delivery_notification_url", 
        "http://localhost:8000/api/v1/mock-agent-listener" # Fallback destination
    )
    
    print(f"[Settlement Engine]: Dispatching release alert to target webhook: {webhook_target}")
    
    # 3. Fire the webhook notification
    webhook_result = trigger_agent_delivery_webhook(
        target_url=webhook_target,
        invoice_id=state["invoice_id"],
        tx_hash=tx_hash,
        product_id=state["target_product_id"]
    )
    
    print(f"[Settlement Engine]: Webhook execution state: {webhook_result['status']}")
    
    return {"xrpl_tx_hash": tx_hash}


def route_after_procurement(state: AgentCommerceState):
    return END if state["procurement_decision"] == "ABORT" else "risk_auditor"

def route_after_audit(state: AgentCommerceState):
    return END if state["auditor_approved"] is False else "settlement_engine"

workflow = StateGraph(AgentCommerceState)
workflow.add_node("procurement", procurement_agent_node)
workflow.add_node("risk_auditor", risk_auditor_agent_node)
workflow.add_node("settlement_engine", xrpl_settlement_node)

workflow.add_edge(START, "procurement")
workflow.add_conditional_edges("procurement", route_after_procurement)
workflow.add_conditional_edges("risk_auditor", route_after_audit)
workflow.add_edge("settlement_engine", END)

compiled_agent_graph = workflow.compile(checkpointer=MemorySaver(), interrupt_before=["settlement_engine"])
