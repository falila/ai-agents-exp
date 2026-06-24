# Solution Architecture Team Graph

A containerized multi-agent state machine utilizing **LangGraph** to automate technical blueprinting. It implements an **Orchestrator + Parallel Specialist Fan-Out/Fan-In** topology to handle concurrent domain analysis before running a centralized validation gate.

## 🏗️ Architectural Topology

The graph maps a single execution payload across parallel branches, synchronization points, and a cyclical quality feedback loop:

```
                  +--------------------+
                  |   lead_architect   |
                  +---------+----------+
                            |
         +------------------+------------------+
         |                  |                  |
         v                  v                  v
+-----------------+ +---------------+ +------------------+
| compute_worker  | |  data_worker  | | security_worker  |
+--------+--------+ +-------+-------+ +--------+---------+
         |                  |                  |
         +------------------+------------------+
                            |
                            v
                  +--------------------+
                  | principal_reviewer |
                  +---------+----------+
                            |
        [Re-draft Needed]   |   [Approved]
                 +----------+----------+
                 |                     |
                 v                     v
         (lead_architect)            (END)

```

### Top-Level Nodes (`agent.py`)

* **`lead_architect_node`**: Triage and scoping agent. Frame-locks bounds and sets the structural constraints payload.
* **`compute_network_specialist_node`**: Parallel isolation thread. Compute stacks (K8s/Serverless), edge topologies, API meshes, and networking fabrics.
* **`data_storage_specialist_node`**: Parallel isolation thread. ACID vs BASE selection, persistence structures (Relational, Document, Vector), and replication/caching topologies.
* **`security_compliance_specialist_node`**: Parallel isolation thread. IAM, encryption vectors (transit/rest), threat modeling, and regulatory mappings (PCI/SOC2).
* **`principal_reviewer_node`**: State consolidation layer. Evaluates against the Well-Architected framework. Emits `ARCHITECTURE_APPROVED` to exit (`END`), or returns `re_draft` to cycle the state back to the orchestrator.

---



---

## 🛠️ Local Setup & Dependency Management

Dependencies and virtual environments are managed via **Astral UV**.

```bash
# Provision isolated venv & activate
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install the core LangGraph runtime toolchain
uv pip install langgraph langgraph-cli langchain-openai

# Freeze for the local Docker builder manifest
uv pip freeze > requirements.txt

```

---

## 🚀 Local Runtime Execution (Docker Daemon Required)

The local dev loop provisions a PostgreSQL state checkpoint database container behind an optimized API engine with automatic hot-reloading.

### 1. Configure the Manifest (`langgraph.json`)

```json
{
  "dependencies": ["."],
  "graphs": {
    "architecture_team": "./agent.py:app"
  },
  "env": {
    "OPENAI_API_KEY": "your_openai_api_key_here"
  }
}

```

### 2. Up the Containers

```bash
langgraph dev

```

*Outputs: Local API exposed at `http://localhost:2024` and an ephemeral hook to the **LangGraph Studio UI** for localized visual tracing and step-by-step state inspection.*

---

## 🧪 Scripted Integration Test

Execute a test run over the local thread executor using `uv run test_run.py`:

```python
from langgraph.pregel.remote import RemoteGraph

# Bound local container endpoint
graph = RemoteGraph(
    graph_id="architecture_team",
    url="http://localhost:2024"
)

payload = {
    "messages": [{
        "role": "user", 
        "content": "Real-time stream engine: 10k ev/sec, <500ms end-to-end latency, CMK encryption at rest, SOC2 compliant."
    }]
}

# Stream parallel steps across the state reducers
for event in graph.stream(payload, config={"configurable": {"thread_id": "tx_001"}}):
    for node, state in event.items():
        print(f"\n[Node: {node.upper()}]\n{state['messages'][-1].get('content', '')}")

```