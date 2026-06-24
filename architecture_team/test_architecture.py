from langgraph.pregel.remote import RemoteGraph

# Connect directly to your local Docker execution engine
graph = RemoteGraph(
    graph_id="architecture_team",
    url="http://localhost:2024"
)

raw_requirements = """
We need to build a financial transaction processing system. 
- It must handle 5,000 requests per second at peak.
- Transactions must have a maximum processing latency of under 100ms.
- It must comply with PCI-DSS regulations (data masking, audit logs, isolated networks).
- Storage must maintain absolute data integrity (ACID compliance required).
- Budget is limited, so serverless components are preferred if they meet the performance limits.
"""

inputs = {"messages": [{"role": "user", "content": raw_requirements}]}
config = {"configurable": {"thread_id": "fintech_project_001"}}

print("🚀 Activating Solution Architecture Multi-Agent Team...")
for event in graph.stream(inputs, config=config):
    for node, state in event.items():
        print(f"\n=======================================================")
        print(f"🏢 Node Executed: {node.upper()}")
        print(f"=======================================================")
        print(state["messages"][-1].get("content", ""))