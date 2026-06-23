from agno.vectordb.chroma import ChromaDb
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from .config import CHROMA_PATH, COLLECTION_NAME


def init_chroma():
    """Create or open the local ChromaDB collection."""
    embedder = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    chroma = ChromaDb(
        collection=COLLECTION_NAME,
        path=str(CHROMA_PATH),
        embedder=embedder,
        persistent_client=True,
    )

    try:
        chroma.client.get_collection(name=COLLECTION_NAME)
    except Exception:
        chroma.create()

    return chroma


def store_documents(chroma_client, documents):
    """Persist document chunks in the Chroma collection."""
    collection = chroma_client.client.get_collection(name=COLLECTION_NAME)
    ids = [str(i) for i in range(len(documents))]
    texts = [doc.page_content for doc in documents]
    metadatas = [doc.metadata for doc in documents]
    collection.add(ids=ids, documents=texts, metadatas=metadatas)


def retrieve_documents(prompt, chroma_client, n_results=5):
    """Query the local vector store for relevant text chunks."""
    collection = chroma_client.client.get_collection(name=COLLECTION_NAME)
    results = collection.query(query_texts=[prompt], n_results=n_results)
    docs = results.get("documents", [])
    return docs, len(docs) > 0
