import pytest
from app.ingest import split_texts
from langchain.docstore.document import Document


def test_split_texts_returns_non_empty_chunks():
    docs = [Document(page_content="Hello world." * 100, metadata={})]
    chunks = split_texts(docs)
    assert len(chunks) > 0
    assert all(chunk.page_content.strip() for chunk in chunks)
