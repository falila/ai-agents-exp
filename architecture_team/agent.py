import os
from typing import Annotated, Sequence, TypedDict, List
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

# =====================================================================
# 1. State Definition
# =====================================================================
class ArchitectureState(TypedDict):
    """
    Tracks the graph's runtime execution state.
    We use the add_messages reducer so that when parallel agents write 
    simultaneously, their outputs append cleanly without collision.
    """
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next_action: str

# Lower temperature to ensure structured, highly factual engineering design
llm = ChatOpenAI(model="gpt-4o", temperature=0.1)

# =====================================================================
# 2. Agent Node Definitions (Orchestrator & Parallel Specialists)
# =====================================================================

def lead_architect_node(state: ArchitectureState):
    """
    NODE 1: The Orchestrator (Lead Solution Architect).
    Triage and scope definition. Sets the foundational technical vision.
    """
    messages = state['messages']
    system_prompt = SystemMessage(content=(
        "You are the Lead Solution Architect. Analyze the user's requirements. "
        "Create a clear, high-level structural breakdown framing the core goals, "
        "scale expectations, and operational bounds of the system.\n"
        "Your breakdown will serve as the explicit operational frame for the "
        "specialists running in parallel immediately after you."
    ))
    
    response = llm.invoke([system_prompt] + messages)
    return {
        "messages": [response],
        "next_action": "fan_out"
    }


def compute_network_specialist_node(state: ArchitectureState):
    """
    NODE 2: Specialist A (Compute & Network Engineering).
    """
    messages = state['messages']
    system_prompt = SystemMessage(content=(
        "You are a Principal Cloud & Network Infrastructure Engineer. Focus EXCLUSIVELY on:\n"
        "1. Compute Topologies: Serverless (Lambda/Functions) vs Containers (K8s/ECS) vs VMs.\n"
        "2. Network Engineering: Subnets, VPCs, Firewalls, API Gateways, Load Balancers, and CDN strategy.\n"
        "3. Integration Patterns: Event-driven pub/sub mesh vs synchronous REST/gRPC.\n"
        "Rely on the requirements context. Do not document storage or IAM; focus purely on the compute/network fabric."
    ))
    
    response = llm.invoke([system_prompt] + messages)
    return {"messages": [response]}


def data_storage_specialist_node(state: ArchitectureState):
    """
    NODE 3: Specialist B (Data & Storage Architecture).
    """
    messages = state['messages']
    system_prompt = SystemMessage(content=(
        "You are a Principal Data Architect. Focus EXCLUSIVELY on:\n"
        "1. Database Engine Selection: Relational (ACID compliance) vs NoSQL (High scale/Document) vs Vector Databases.\n"
        "2. State Management & Cache: In-memory caching layers (Redis/Memcached) and write/read strategies.\n"
        "3. Replication & Partitioning: High availability clusters, shards, read-replicas, and data lifecycle archiving plans.\n"
        "Do not write about API Gateways or security firewalls; focus entirely on the data persistence tier."
    ))
    
    response = llm.invoke([system_prompt] + messages)
    return {"messages": [response]}


def security_compliance_specialist_node(state: ArchitectureState):
    """
    NODE 4: Specialist C (Security & Compliance Officer).
    """
    messages = state['messages']
    system_prompt = SystemMessage(content=(
        "You are a Principal Cloud Security Architect and Compliance Officer. Focus EXCLUSIVELY on:\n"
        "1. IAM Frameworks: Authentication & Authorization layers (OAuth2, OIDC, RBAC, Least Privilege policies).\n"
        "2. Data Protection: Encryption algorithms and key management strategies at rest and in transit.\n"
        "3. Audit & Compliance: Threat modeling against vulnerabilities, masking, and matching regulatory frameworks (e.g., PCI-DSS, GDPR, HIPAA).\n"
        "Focus purely on securing the landscape and proving compliance."
    ))
    
    response = llm.invoke([system_prompt] + messages)
    return {"messages": [response]}


def principal_reviewer_node(state: ArchitectureState):
    """
    NODE 5: The Gatekeeper (Principal Board Reviewer).
    Consolidates parallel streams, applies the Well-Architected Framework, and judges stability.
    """
    messages = state['messages']
    system_prompt = SystemMessage(content=(
        "You are the Principal Board Reviewer. Evaluate the consolidated inputs from the "
        "Compute, Data, and Security specialists against the AWS/Azure Well-Architected Framework.\n\n"
        "Your task is to either:\n"
        "1. Formulate a final unified Master Solution Architecture Document and sign off.\n"
        "2. Decline the draft if any domain specialist left critical gaps, missed latency SLA targets, "
        "   or introduced architectural vulnerabilities.\n\n"
        "CRITICAL RULES:\n"
        "- If everything is structurally sound and production-ready, compile the final blueprint "
        "  and conclude your response with the exact token: 'ARCHITECTURE_APPROVED'.\n"
        "- If revisions are necessary, do NOT include that token. Provide granular feedback on what needs refinement."
    ))
    
    response = llm.invoke([system_prompt] + messages)
    
    if "ARCHITECTURE_APPROVED" in response.content.upper():
        next_step = "finish"
    else:
        next_step = "re_draft"
        
    return {
        "messages": [response],
        "next_action": next_step
    }

# =====================================================================
# 3. Graph Routing & Topology Construction (Parallel Fan-Out/Fan-In)
# =====================================================================

def route_after_review(state: ArchitectureState):
    """Evaluates whether the board approved the design or needs another loop."""
    if state["next_action"] == "finish":
        return END
    return "lead_architect"


# Initialize the state-aware graph workflow
workflow = StateGraph(ArchitectureState)

# Append architectural nodes to the topology
workflow.add_node("lead_architect", lead_architect_node)
workflow.add_node("compute_worker", compute_network_specialist_node)
workflow.add_node("data_worker", data_storage_specialist_node)
workflow.add_node("security_worker", security_compliance_specialist_node)
workflow.add_node("principal_reviewer", principal_reviewer_node)

# Set Entry Point
workflow.set_entry_point("lead_architect")

# Parallel Fan-Out (Broadcast execution from Orchestrator to all specialists simultaneously)
workflow.add_edge("lead_architect", "compute_worker")
workflow.add_edge("lead_architect", "data_worker")
workflow.add_edge("lead_architect", "security_worker")

# Parallel Fan-In (LangGraph naturally waits until ALL incoming nodes complete before moving forward)
workflow.add_edge("compute_worker", "principal_reviewer")
workflow.add_edge("data_worker", "principal_reviewer")
workflow.add_edge("security_worker", "principal_reviewer")

# Quality Gate Conditional Edge
workflow.add_conditional_edges(
    "principal_reviewer",
    route_after_review,
    {
        END: END,
        "lead_architect": "lead_architect"
    }
)

# Compile graph application instance
app = workflow.compile()