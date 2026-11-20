"""Hybrid retrieval: BM25 + dense (FAISS) -> reciprocal rank fusion -> LLM re-rank.

Superseded versions (an older version of the same doc_id) are excluded by default,
so the assistant prefers the latest version of every document.
"""
import json
import re
from pathlib import Path

import faiss
import numpy as np
from rank_bm25 import BM25Okapi

from config import POOL, RRF_K
from ingest import embed

INDEX_DIR = Path(__file__).resolve().parent.parent / "index"
TOKEN = re.compile(r"\w+")


def tok(s: str):
    return TOKEN.findall(s.lower())


class Retriever:
    def __init__(self):
        meta = json.loads((INDEX_DIR / "meta.json").read_text())
        self.kind = meta["embedder"]
        self.index = faiss.read_index(str(INDEX_DIR / "faiss.index"))
        self.chunks = [json.loads(l) for l in open(INDEX_DIR / "chunks.jsonl", encoding="utf-8")]
        self.bm25 = BM25Okapi([tok(c["text"]) for c in self.chunks])
        latest = {}
        for c in self.chunks:
            d = c["doc_id"]
            if d not in latest or c["effective_date"] > latest[d]:
                latest[d] = c["effective_date"]
        self.active = np.array([c["effective_date"] == latest[c["doc_id"]] for c in self.chunks])

    def _dense(self, query, pool, include_old):
        qv = embed([query], self.kind, "RETRIEVAL_QUERY")
        _, ids = self.index.search(qv, len(self.chunks))
        ranked = [i for i in ids[0] if include_old or self.active[i]]
        return ranked[:pool]

    def _sparse(self, query, pool, include_old):
        scores = self.bm25.get_scores(tok(query))
        order = np.argsort(-scores)
        return [int(i) for i in order if scores[i] > 0 and (include_old or self.active[i])][:pool]

    def search(self, query, k=4, pool=POOL, include_old=False, rerank_fn=None):
        dense = self._dense(query, pool, include_old)
        sparse = self._sparse(query, pool, include_old)
        fused = {}
        for ranking in (dense, sparse):
            for r, i in enumerate(ranking):
                fused[i] = fused.get(i, 0.0) + 1.0 / (RRF_K + r + 1)
        cand = sorted(fused, key=fused.get, reverse=True)[:8]
        if rerank_fn:
            try:
                cand = rerank_fn(query, [self.chunks[i] for i in cand], cand)
            except Exception:
                pass                                   # fall back to fused order
        return [dict(self.chunks[i], score=round(fused.get(i, 0.0), 4)) for i in cand[:k]]


def llm_rerank(query, chunks, idxs):
    """One Gemini call: order candidates by usefulness for the question."""
    from llm import generate_json
    listing = "\n".join(f"[{n}] {c['title']}: {c['text'][:350]}" for n, c in enumerate(chunks))
    data, _ = generate_json(
        "You rank passages by how directly they answer the question. "
        'Return JSON: {"order": [passage numbers, best first]}.',
        f"Question: {query}\n\nPassages:\n{listing}")
    order = [n for n in data["order"] if isinstance(n, int) and 0 <= n < len(idxs)]
    order += [n for n in range(len(idxs)) if n not in order]
    return [idxs[n] for n in order]
