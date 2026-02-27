from typing import List, Dict, Any
from .vector_store import FaissStore
from .embedder import Embedder

class Retriever:
    def __init__(self, store: FaissStore, embedder: Embedder, top_k: int = 6):
        self.store = store
        self.embedder = embedder
        self.top_k = top_k

    def retrieve(self, question: str) -> List[Dict[str, Any]]:
        qv = self.embedder.embed_query(question)
        hits = self.store.search(qv, self.top_k)

        out = []
        for score, meta in hits:
            out.append({"score": score, **meta})
        return out
