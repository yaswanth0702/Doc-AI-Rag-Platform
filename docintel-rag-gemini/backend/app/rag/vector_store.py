import os
import json
from typing import List, Dict, Any, Tuple
import numpy as np
import faiss

class FaissStore:
    """
    Keeps:
      - faiss.index for vectors
      - metadata.jsonl aligned with vector IDs
    """
    def __init__(self, index_dir: str):
        self.index_dir = index_dir
        os.makedirs(self.index_dir, exist_ok=True)

        self.index_path = os.path.join(self.index_dir, "faiss.index")
        self.meta_path = os.path.join(self.index_dir, "metadata.jsonl")

        self.index = None
        self.metadata: List[Dict[str, Any]] = []

        self._load()

    def _load(self):
        if os.path.exists(self.index_path) and os.path.exists(self.meta_path):
            self.index = faiss.read_index(self.index_path)
            self.metadata = []
            with open(self.meta_path, "r", encoding="utf-8") as f:
                for line in f:
                    self.metadata.append(json.loads(line))
        else:
            self.index = None
            self.metadata = []

    def _save(self):
        if self.index is not None:
            faiss.write_index(self.index, self.index_path)
        with open(self.meta_path, "w", encoding="utf-8") as f:
            for m in self.metadata:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")

    def add(self, vectors: np.ndarray, metas: List[Dict[str, Any]]) -> int:
        if len(vectors) == 0:
            return 0

        dim = vectors.shape[1]
        if self.index is None:
            # normalized vectors -> inner product acts like cosine similarity
            self.index = faiss.IndexFlatIP(dim)

        self.index.add(vectors)
        self.metadata.extend(metas)
        self._save()
        return len(vectors)

    def search(self, query_vec: np.ndarray, top_k: int) -> List[Tuple[float, Dict[str, Any]]]:
        if self.index is None or len(self.metadata) == 0:
            return []

        q = np.asarray([query_vec], dtype="float32")
        scores, ids = self.index.search(q, top_k)

        results = []
        for score, idx in zip(scores[0], ids[0]):
            if idx == -1:
                continue
            results.append((float(score), self.metadata[int(idx)]))
        return results
