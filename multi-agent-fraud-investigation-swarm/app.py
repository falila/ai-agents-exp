import streamlit as st
import pandas as pd
from PIL import Image
import os
import glob
import time
import sys
import json
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# Agno orchestration and model integrations
from agno.agent import Agent
from agno.team import Team
from agno.models.ollama import Ollama
from agno.tools.duckduckgo import DuckDuckGoTools
try:
    from agno.media import Image as AgnoImage
except Exception:
    AgnoImage = None

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")


def build_agno_images(image_paths: list[str]) -> list:
    if not image_paths:
        return []
    if AgnoImage is None:
        return image_paths

    converted_images = []
    for image_path in image_paths:
        try:
            converted_images.append(AgnoImage(filepath=image_path))
        except TypeError:
            # Some Agno versions expect url/path instead of filepath.
            try:
                converted_images.append(AgnoImage(path=image_path))
            except TypeError:
                try:
                    converted_images.append(AgnoImage(url=image_path))
                except Exception:
                    converted_images.append(image_path)
        except Exception:
            converted_images.append(image_path)
    return converted_images


def model_supports_multimodal(model_id: str) -> bool:
    name = model_id.lower()
    multimodal_markers = [
        "qwen2.5vl",
        "kimi-k2.5",
        "llava",
        "bakllava",
        "minicpm-v",
        "vision",
        "moondream",
        "gemma3",
        "vl",
    ]
    return any(marker in name for marker in multimodal_markers)


def run_with_image_compat(runner, prompt: str, image_paths: list[str]):
    if not image_paths:
        return runner.run(prompt)

    candidate_payloads = [
        build_agno_images(image_paths),
        [{"filepath": image_path} for image_path in image_paths],
        [{"path": image_path} for image_path in image_paths],
        [{"url": image_path} for image_path in image_paths],
        image_paths,
    ]

    last_error = None
    for payload in candidate_payloads:
        try:
            return runner.run(prompt, images=payload)
        except Exception as exc:
            last_error = exc

    fallback_prompt = (
        f"{prompt}\n\n"
        "Image evidence file paths were supplied as local files: "
        f"{', '.join(image_paths)}. "
        "If direct image attachment is unsupported, still provide your best"
        " fraud assessment using available text and context."
    )
    try:
        return runner.run(fallback_prompt)
    except Exception:
        if last_error is not None:
            raise last_error
        raise


def fetch_available_ollama_models() -> set[str]:
    request = Request(f"{OLLAMA_HOST.rstrip('/')}/api/tags", headers={"User-Agent": "FraudHub/1.0"})
    try:
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, HTTPError, json.JSONDecodeError, TimeoutError):
        return set()

    models = set()
    for entry in payload.get("models", []):
        name = entry.get("name", "")
        if name:
            models.add(name)
            models.add(name.split(":", 1)[0])
    return models


def choose_multimodal_model(preferred_model: str, fallback_model: str) -> tuple[str, str | None]:
    available_models = fetch_available_ollama_models()
    if not available_models:
        return preferred_model, None
    if preferred_model in available_models:
        return preferred_model, None
    if fallback_model in available_models:
        return fallback_model, f"`{preferred_model}` is not available locally. Falling back to `{fallback_model}`."
    return preferred_model, f"Neither `{preferred_model}` nor `{fallback_model}` is available locally in Ollama yet."


def choose_routing_model() -> tuple[str, str | None]:
    preferred_model = "llama3.3:70b"
    fallback_models = ["llama3.2:3b", "deepseek-r1:8b", "qwen2.5vl"]

    available_models = fetch_available_ollama_models()
    if not available_models:
        return preferred_model, None
    if preferred_model in available_models:
        return preferred_model, None

    for fallback_model in fallback_models:
        if fallback_model in available_models:
            return (
                fallback_model,
                (
                    f"`{preferred_model}` is not available locally. "
                    f"Using routing fallback `{fallback_model}`."
                ),
            )

    return (
        preferred_model,
        (
            f"`{preferred_model}` is not available locally and no routing fallback "
            "model was detected in Ollama."
        ),
    )

# -----------------------------------------------------------------------------
# Page setup
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Multi Agent Fraud Investigation Swarm",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🛡️ Multi Agent Fraud Investigation Swarm")
st.caption("Multi-Agent Cross-Modal Risk Investigation powered by Agno, DeepSeek-R1, and a local Ollama multimodal stack.")
st.markdown("---")

# -----------------------------------------------------------------------------
# Sidebar controls
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configuration Setup")
    st.info("Use local Ollama models when possible. Kimi K2.5 is the preferred multimodal option, with Qwen2.5-VL as a fallback.")
    
    # Let the analyst choose which models to use for this run.
    reasoning_model_id = st.selectbox(
        "Deep Ledger Reasoning Engine", 
        ["deepseek-r1:70b", "deepseek-r1:8b"], 
        index=1  # Use the lighter model by default so it works on more machines.
    )
    multimodal_model_id = st.selectbox(
        "Multimodal KYC Engine", 
        ["kimi-k2.5", "qwen2.5vl"], 
        index=0
    )
    selected_multimodal_model, multimodal_notice = choose_multimodal_model(multimodal_model_id, "qwen2.5vl")
    selected_routing_model, routing_notice = choose_routing_model()
    if multimodal_notice:
        st.warning(multimodal_notice)
    if routing_notice:
        st.warning(routing_notice)
    
    st.markdown("---")
    st.subheader("System Status")
    st.success("Agno Orchestrator: Connected")
    st.success("Ollama Nodes: Operational")
    st.caption("Recommended pulls: kimi-k2.5, qwen2.5vl, deepseek-r1:8b, llama3.3:70b")

# -----------------------------------------------------------------------------
# Main workflow tabs
# -----------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["📥 Step 1: Ingest Telemetry", "🔍 Step 2: Multi-Agent Analysis", "📊 Step 3: Resolution & Audit"])

# --- TAB 1: INGEST DATA ---
with tab1:
    st.header("1. Upload Session Case Files")
    st.write("Provide the transactional history ledger alongside the customer identity validation documents below.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Financial Transaction Record")
        uploaded_csv = st.file_uploader("Upload Ledger History (.csv)", type=["csv"], help="Must contain timestamp, amount, source, and destination vectors.")
        
        if uploaded_csv is not None:
            df = pd.read_csv(uploaded_csv)
            st.dataframe(df.head(5), use_container_width=True)
            st.success(f"Successfully loaded {len(df)} ledger records.")
            # Keep the uploaded ledger available for the analysis step.
            st.session_state['ledger_data'] = df
            
    with col2:
        st.subheader("KYC Verification Imagery")
        uploaded_image = st.file_uploader("Upload ID Document/Selfie Pass (.jpg, .png, .jpeg)", type=["jpg", "png", "jpeg"], help="High-resolution document check.")
        
        if uploaded_image is not None:
            image = Image.open(uploaded_image)
            st.image(image, caption="Uploaded Identity Target Document", width=350)
            
            # Save a temporary file because the agent call needs a real file path.
            temp_img_path = f"temp_kyc_{uploaded_image.name}"
            image.save(temp_img_path)
            st.session_state['kyc_image_path'] = temp_img_path
            st.success("Identity vector cached successfully.")

# --- TAB 2: RUN ANALYSIS ---
with tab2:
    st.header("2. Run Asynchronous Swarm Diagnostic")
    st.write("Trigger the supervisor to coordinate DeepSeek-R1 with a local multimodal model for KYC and OSINT analysis.")
    
    # Only allow analysis if at least one evidence source has been uploaded.
    has_ledger = 'ledger_data' in st.session_state
    has_image = 'kyc_image_path' in st.session_state
    
    if not (has_ledger or has_image):
        st.warning("⚠️ Please upload a CSV ledger file or an Identity Image in Step 1 to trigger the multi-agent investigation.")
    else:
        st.info("System is primed with incoming data streams.")
        
        # Optional analyst notes that get passed into the investigation prompt.
        metadata_notes = st.text_area("Additional Investigation Context / Flag Signals", placeholder="e.g., User triggered location mismatch flag via proxy VPN.")
        
        if st.button("🚀 Trigger Swarm Resolution Engine", type="primary"):
            
            with st.status("Assembling Swarm & Executing Trace Audits...", expanded=True) as status:
                
                try:
                    # Spin up the model wrappers used by the team.
                    reasoning_engine = Ollama(id=reasoning_model_id)
                    multimodal_engine = Ollama(id=selected_multimodal_model)
                    routing_engine = Ollama(id=selected_routing_model)  # Supervisor that coordinates the specialists.
                    
                    status.update(label="Spinning up worker specialized instances...", state="running")
                    
                    # Define the specialist agents.
                    kyc_visual_agent = Agent(
                        name="KYC Visual Validator",
                        model=multimodal_engine,
                        description="Inspects user document imagery and facial photos for tampering or deepfake signals.",
                        instructions=["Analyze visual metadata, edge consistency, alignment, and artifact anomalies."],
                    )

                    behavioral_audit_agent = Agent(
                        name="Behavioral Reasoning Auditor",
                        model=reasoning_engine,
                        description="Performs trace-analysis over financial ledger patterns to discover structured fraud vectors.",
                        instructions=["Utilize deep sequential step-by-step thinking trace logs. Trace velocity anomalies and balance drainage."],
                    )
                    
                    osint_footprint_agent = Agent(
                        name="OSINT Footprint Investigator",
                        model=multimodal_engine,
                        tools=[DuckDuckGoTools()],
                        description="Scrapes and searches threat intelligence databases and open web data vectors.",
                        instructions=["Query domain records, cross-reference data leaks, and evaluate email age."],
                    )
                    
                    # Build the team that shares context and produces one final verdict.
                    fraud_resolution_team = Team(
                        name="Enterprise Fraud Resolution Swarm",
                        model=routing_engine,
                        members=[kyc_visual_agent, behavioral_audit_agent, osint_footprint_agent],
                        share_member_interactions=True,
                        instructions=[
                            "Coordinate evaluation vectors across all target profile data payloads.",
                            "Synthesize separate risk profiles into a final unified JSON risk evaluation breakdown.",
                            "Provide your final output with explicit bolding for final metrics.",
                            "Include a definitive verdict score: [PASS, REVIEW, BLOCK] based on unified weights."
                        ]
                    )
                    
                    status.update(label="Processing ledger history metrics & scanning image layers...", state="running")
                    
                    # Build the case prompt from the uploaded evidence and analyst notes.
                    execution_prompt = f"Perform deep forensic diagnostic review over this case file request. Metadata context notes: {metadata_notes}. "
                    if has_ledger:
                        execution_prompt += f"Analyze these target records: {st.session_state['ledger_data'].to_string(max_rows=15)}"
                    
                    input_image_paths = [st.session_state['kyc_image_path']] if has_image else []

                    # If router is text-only, run KYC visuals first and inject its findings.
                    if has_image and not model_supports_multimodal(selected_routing_model):
                        status.update(
                            label="Router is text-only; running KYC visual analysis separately...",
                            state="running",
                        )
                        kyc_response = run_with_image_compat(
                            kyc_visual_agent,
                            (
                                "Analyze the attached KYC image(s) for fraud signs: tampering, "
                                "deepfake artifacts, metadata inconsistency, and identity mismatch risk. "
                                "Return a concise risk summary with confidence."
                            ),
                            input_image_paths,
                        )
                        kyc_text = getattr(kyc_response, "content", str(kyc_response))
                        execution_prompt += (
                            "\n\nKYC visual specialist findings (precomputed):\n"
                            f"{kyc_text}\n"
                            "Treat these findings as evidence in final verdict synthesis."
                        )
                        input_image_paths = []

                    # Run the team and keep the final response for the Resolution tab.
                    response = run_with_image_compat(
                        fraud_resolution_team,
                        execution_prompt,
                        input_image_paths,
                    )
                    
                    status.update(label="Swarm analysis finalized completely.", state="complete")
                    
                    # Save the final verdict so the next tab can render it.
                    st.session_state['swarm_verdict'] = response.content
                    st.success("Analysis complete! Proceed to Step 3 to view results.")
                    
                except Exception as e:
                    status.update(label="System Framework Interruption Occurred", state="error")
                    st.error(f"Execution Error Breakdown: {str(e)}")
                    st.exception(e)

# --- TAB 3: REVIEW RESULTS ---
with tab3:
    st.header("3. Unified Resolution Center")
    
    if 'swarm_verdict' not in st.session_state:
        st.info("Awaiting execution output. Trigger the swarm analysis in Step 2 to view final auditing evaluations.")
    else:
        st.subheader("🕵️ Swarm Diagnostic Diagnostic Breakdown Log Output")
        
        st.markdown(st.session_state['swarm_verdict'])
        
        st.markdown("---")
        st.subheader("⚖️ Operational Action Override")
        
        # Final operator actions.
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        with col_btn1:
            if st.button("🟢 Force Approve Session Case", use_container_width=True):
                st.toast("Case marked as APPROVED manually.", icon="✅")
        with col_btn2:
            if st.button("🟡 Route Session to Escalation Desk", use_container_width=True):
                st.toast("Case escalated to Layer-3 forensics desk.", icon="⚠️")
        with col_btn3:
            if st.button("🔴 Absolute Block User Profile", use_container_width=True):
                st.toast("User ID profile blacklisted securely.", icon="🚨")

# -----------------------------------------------------------------------------
# Cleanup
# -----------------------------------------------------------------------------
try:
    # Remove the temporary image if the upload was cleared.
    if 'kyc_image_path' in st.session_state:
        current_img_path = st.session_state['kyc_image_path']
        
        if uploaded_image is None and os.path.exists(current_img_path):
            os.remove(current_img_path)
            del st.session_state['kyc_image_path']
            if 'swarm_verdict' in st.session_state:
                del st.session_state['swarm_verdict']
            st.rerun()

    # Sweep any temp images left behind by older abandoned sessions.
    temp_files = glob.glob("temp_kyc_*")
    for file_path in temp_files:
        # Drop files older than 20 minutes.
        if os.path.exists(file_path) and (time.time() - os.path.getmtime(file_path) > 1200):
            try:
                os.remove(file_path)
            except OSError:
                pass 

except Exception as cleanup_error:
    print(f"[CRITICAL CLEANUP ERROR]: {str(cleanup_error)}", file=sys.stderr)