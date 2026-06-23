import tempfile
from datetime import datetime

from langchain_community.document_loaders import PyPDFLoader, WebBaseLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def split_texts(documents):
    """Split documents into overlapping chunks for retrieval."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    split_docs = splitter.split_documents(documents)

    return [
        Document(page_content=doc.page_content, metadata=doc.metadata)
        for doc in split_docs
        if doc.page_content.strip()
    ]


def process_pdf(uploaded_file):
    """Load PDF content and attach metadata."""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(uploaded_file.read())
            loader = PyPDFLoader(tmp_file.name)
            documents = loader.load()

        for doc in documents:
            doc.metadata.update({
                "source_type": "pdf",
                "file_name": uploaded_file.name,
                "timestamp": datetime.now().isoformat(),
            })

        return split_texts(documents)
    except Exception as exc:
        raise RuntimeError(f"PDF processing failed: {exc}") from exc


def process_web(url: str):
    """Load web page content and attach metadata."""
    try:
        loader = WebBaseLoader(url)
        documents = loader.load()

        for doc in documents:
            doc.metadata.update({
                "source": url,
                "timestamp": datetime.now().isoformat(),
            })

        return split_texts(documents)
    except Exception as exc:
        raise RuntimeError(f"Web page processing failed: {exc}") from exc
