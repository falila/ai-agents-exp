from app.retrieval import retrieve_documents


def test_retrieve_documents_handles_empty_store():
    class DummyClient:
        def __init__(self):
            self.client = self

        def get_collection(self, name):
            class Collection:
                def query(self, query_texts, n_results):
                    return {"documents": []}
            return Collection()

    dummy = DummyClient()
    docs, has_docs = retrieve_documents("test", dummy)
    assert docs == []
    assert has_docs is False
