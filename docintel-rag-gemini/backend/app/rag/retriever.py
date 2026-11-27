import math
import re
from collections import Counter

from .embedder import Embedder
from .vector_store import FaissStore


def terms(text: str):
    # Keep identifiers intact while allowing searches for an individual component.
    for token in re.findall(r"\w+(?:[-./]\w+)*", text.casefold()):
        yield token
        if re.search(r"[-./_]", token):
            yield from filter(None, re.split(r"[-./_]+", token))


def keyword_ranks(question, passages):
    wanted = set(terms(question))
    counts = []
    lengths = []
    document_frequency = Counter()
    for passage in passages:
        tokens = list(terms(passage["text"]))
        matches = Counter(token for token in tokens if token in wanted)
        counts.append(matches)
        lengths.append(len(tokens))
        document_frequency.update(matches.keys())

    average_length = sum(lengths) / len(passages) or 1
    scores = {}
    for passage, matches, length in zip(passages, counts, lengths):
        if not matches:
            continue
        # BM25 length normalization and inverse document frequency.
        norm = 1.2 * (0.25 + 0.75 * length / average_length)
        score = 0.0
        for word, frequency in matches.items():
            df = document_frequency[word]
            idf = math.log1p((len(passages) - df + 0.5) / (df + 0.5))
            score += idf * frequency * 2.2 / (frequency + norm)
        scores[passage["chunk_id"]] = score

    ordered = sorted(scores, key=scores.get, reverse=True)
    return {chunk_id: rank for rank, chunk_id in enumerate(ordered, 1)}


def passages_on_page(passages, page: int | None):
    if page is None:
        return passages
    return [passage for passage in passages if passage.get("page") == page]


def exact_passages(query, passages, limit):
    phrase = " ".join(query.casefold().split())
    matches = []
    for passage in passages:
        if phrase and phrase in " ".join(passage["text"].casefold().split()):
            matches.append(passage)
            if len(matches) >= limit:
                break
    return matches


class Retriever:
    def __init__(self, store: FaissStore, embedder: Embedder, top_k: int = 6):
        self.store = store
        self.embedder = embedder
        self.top_k = top_k

    def retrieve(self, question: str, page: int | None = None) -> list[dict]:
        passages = passages_on_page(self.store.metadata, page)
        if not passages or self.top_k <= 0:
            return []
        vector = self.embedder.embed_query(question)
        hits = self.store.search(vector, len(self.store.metadata))
        if page is not None:
            # Compute both rank positions within the page before combining them or applying top_k.
            hits = [(score, row) for score, row in hits if row.get("page") == page]
        lexical = keyword_ranks(question, passages)
        ranked = []
        for semantic_rank, (score, passage) in enumerate(hits, 1):
            # Combine rank positions because lexical and vector scores use different scales.
            priority = 1 / (60 + semantic_rank)
            lexical_rank = lexical.get(passage["chunk_id"])
            if lexical_rank is not None:
                priority += 1 / (60 + lexical_rank)
            ranked.append((priority, {"score": score, **passage}))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [passage for _, passage in ranked[:self.top_k]]
