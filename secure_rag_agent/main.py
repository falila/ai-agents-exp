import streamlit as st
from dotenv import load_dotenv

from app.config import (
    CHROMA_PATH,
    COLLECTION_NAME,
    MODEL_VERSION,
    RAG_ENABLED_DEFAULT,
    SIMILARITY_THRESHOLD,
    USE_WEB_SEARCH_DEFAULT,
)
from app.ingest import process_pdf, process_web
from app.retrieval import init_chroma, retrieve_documents, store_documents
from app.agent import get_rag_agent, get_web_search_agent
from app.utils import filter_think_tags

load_dotenv()


def initialize_session_state():
    defaults = {
        "chroma_path": CHROMA_PATH,
        "model_version": MODEL_VERSION,
        "processed_documents": [],
        "history": [],
        "use_web_search": USE_WEB_SEARCH_DEFAULT,
        "force_web_search": False,
        "similarity_threshold": SIMILARITY_THRESHOLD,
        "rag_enabled": RAG_ENABLED_DEFAULT,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_sidebar():
    st.sidebar.header("🤖 Agent Configuration")
    st.session_state.model_version = st.sidebar.radio(
        "Select Model Version",
        [MODEL_VERSION],
        help="DeepSeek model used for reasoning.",
    )

    st.sidebar.header("🔍 RAG Configuration")
    st.session_state.rag_enabled = st.sidebar.checkbox(
        "Enable RAG Mode",
        value=st.session_state.rag_enabled,
    )

    if st.sidebar.button("🗑️ Reset Conversation History"):
        st.session_state.history = []
        st.experimental_rerun()

    st.sidebar.header("🌐 Web Search Configuration")
    st.session_state.use_web_search = st.sidebar.checkbox(
        "Enable Web Search Fallback",
        value=st.session_state.use_web_search,
    )

    st.sidebar.header("📁 Data Upload")
    uploaded_file = st.sidebar.file_uploader("Upload PDF", type=["pdf"])
    web_url = st.sidebar.text_input("Or enter a URL")

    return uploaded_file, web_url


def main():
    st.set_page_config(page_title="Secure Local RAG  Agent")
    st.title("🐋 Secure Local RAG Agent")

    initialize_session_state()
    uploaded_file, web_url = render_sidebar()

    chroma_client = None
    if st.session_state.rag_enabled:
        chroma_client = init_chroma()

    if uploaded_file and uploaded_file.name not in st.session_state.processed_documents:
        try:
            documents = process_pdf(uploaded_file)
            if documents:
                store_documents(chroma_client, documents)
                st.session_state.processed_documents.append(uploaded_file.name)
                st.success("PDF uploaded and indexed successfully.")
        except RuntimeError as exc:
            st.error(str(exc))

    if web_url and web_url not in st.session_state.processed_documents:
        try:
            documents = process_web(web_url)
            if documents:
                store_documents(chroma_client, documents)
                st.session_state.processed_documents.append(web_url)
                st.success("Web page content indexed successfully.")
        except RuntimeError as exc:
            st.error(str(exc))

    prompt = st.chat_input(
        "Ask your question..." if st.session_state.rag_enabled else "Ask me anything..."
    )

    if prompt:
        st.session_state.history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        context = ""
        if st.session_state.rag_enabled and not st.session_state.force_web_search:
            docs, has_docs = retrieve_documents(prompt, chroma_client)
            if has_docs:
                context = "\n\n".join([paragraph for doc in docs for paragraph in doc])

        if (st.session_state.force_web_search or not context) and st.session_state.use_web_search:
            with st.spinner("🔍 Searching the web..."):
                web_search_agent = get_web_search_agent()
                web_results = web_search_agent.run(prompt).content
                if web_results:
                    context = f"Web Search Results:\n{web_results}"

        with st.spinner("🤖 Generating response..."):
            rag_agent = get_rag_agent(st.session_state.model_version)
            response = rag_agent.run(f"Context: {context}\n\nQuestion: {prompt}").content

        clean_response = filter_think_tags(response)
        st.session_state.history.append({"role": "assistant", "content": clean_response})
        with st.chat_message("assistant"):
            st.write(clean_response)

    elif not st.session_state.history:
        st.warning("Ask a question to begin!")


if __name__ == "__main__":
    main()
