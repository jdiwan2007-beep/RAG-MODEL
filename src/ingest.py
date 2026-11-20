"""Ingestion pipeline: extract -> clean -> chunk (overlap) -> embed -> FAISS.

Usage:
    python src/ingest.py                  # Gemini embeddings (needs GEMINI_API_KEY)
    python src/ingest.py --embedder hash  # offline test mode, no API key
"""
import argparse
import hashlib
import json
import os
import re
import time
from pathlib import Path

import numpy as np
import faiss

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
INDEX_DIR = ROOT / "index"

CHUNK_WORDS = 90      # target words per chunk
OVERLAP_WORDS = 20    # words shared between neighbouring chunks
EMBED_MODEL = "gemini-embedding-001"
EMBED_DIM = 768

NOISE = re.compile(r"^(ELECTROMART INDORE \|.*|Page \d+ of \d+ \|.*)$")
META = re.compile(
    r"Doc ID:\s*(?P<doc_id>[\w-]+)\s*\|\s*Version:\s*(?P<version>\w+)\s*\|\s*"
    r"Department:\s*(?P<department>[\w ]+?)\s*\|\s*Effective:\s*(?P<date>[\d-]+)"
)


# ---------- 1. extract + clean ----------
def table_to_sentences(lines):
    """Turn a markdown table into 'Header: value, Header: value' lines."""
    rows = [[c.strip() for c in l.strip("|").split("|")] for l in lines]
    header, body = rows[0], [r for r in rows[2:] if r]
    return [", ".join(f"{h}: {v}" for h, v in zip(header, r)) + "." for r in body]


def clean(raw: str):
    """Return (metadata, title, cleaned_body)."""
    m = META.search(raw)
    meta = m.groupdict() if m else {}
    lines = [l.rstrip() for l in raw.splitlines()]
    kept = []
    for l in lines:
        if NOISE.match(l.strip()) or META.search(l):
            continue                    # strip repeated headers/footers/meta line
        kept.append(l)
    # convert tables
    out, i = [], 0
    while i < len(kept):
        if kept[i].lstrip().startswith("|"):
            j = i
            while j < len(kept) and kept[j].lstrip().startswith("|"):
                j += 1
            out.extend(table_to_sentences(kept[i:j]))
            i = j
        else:
            out.append(kept[i])
            i += 1
    text = re.sub(r"\n{2,}", "\n", "\n".join(out)).strip()
    title, _, body = text.partition("\n")
    body = re.sub(r"\s+", " ", body).strip()
    return meta, title.strip(), body


# ---------- 2. chunk with overlap ----------
def chunk_words(text: str, size=CHUNK_WORDS, overlap=OVERLAP_WORDS):
    words = text.split()
    if len(words) <= size:
        return [text]
    chunks, step = [], size - overlap
    for start in range(0, len(words), step):
        piece = words[start:start + size]
        chunks.append(" ".join(piece))
        if start + size >= len(words):
            break
    return chunks


def build_chunks():
    chunks = []
    for path in sorted(RAW.glob("*.txt")):
        meta, title, body = clean(path.read_text(encoding="utf-8"))
        for n, piece in enumerate(chunk_words(body)):
            chunks.append({
                "chunk_id": f"{path.stem}#{n}",
                "source_file": path.name,
                "doc_id": meta["doc_id"],
                "version": meta["version"],
                "department": meta["department"],
                "effective_date": meta["date"],
                "title": title,
                # prefixing the title helps both BM25 and embeddings
                "text": f"{title}. {piece}",
            })
    return chunks


# ---------- 3. embed ----------
def embed_hash(texts, dim=EMBED_DIM):
    """Offline stand-in for TESTING the pipeline only. Not semantic."""
    vecs = np.zeros((len(texts), dim), dtype="float32")
    for i, t in enumerate(texts):
        for w in re.findall(r"\w+", t.lower()):
            h = int(hashlib.md5(w.encode()).hexdigest(), 16)
            vecs[i, h % dim] += 1.0
    return vecs


def embed_gemini(texts, task_type="RETRIEVAL_DOCUMENT"):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    vecs = []
    for i in range(0, len(texts), 20):          # small batches for the free tier
        batch = texts[i:i + 20]
        for attempt in range(5):
            try:
                res = client.models.embed_content(
                    model=EMBED_MODEL, contents=batch,
                    config=types.EmbedContentConfig(
                        task_type=task_type, output_dimensionality=EMBED_DIM))
                vecs.extend(e.values for e in res.embeddings)
                break
            except Exception as e:                  # rate limit -> back off
                wait = 10 * (attempt + 1)
                print(f"  embed retry in {wait}s ({e.__class__.__name__})")
                time.sleep(wait)
        else:
            raise RuntimeError("Embedding failed after retries")
        time.sleep(1)
    return np.array(vecs, dtype="float32")


def embed(texts, kind="gemini", task_type="RETRIEVAL_DOCUMENT"):
    v = embed_hash(texts) if kind == "hash" else embed_gemini(texts, task_type)
    faiss.normalize_L2(v)                           # cosine via inner product
    return v


# ---------- 4. store ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--embedder", choices=["gemini", "hash"], default="gemini")
    args = ap.parse_args()

    chunks = build_chunks()
    print(f"{len(chunks)} chunks from {len(list(RAW.glob('*.txt')))} documents")
    vecs = embed([c["text"] for c in chunks], args.embedder)

    index = faiss.IndexFlatIP(vecs.shape[1])
    index.add(vecs)
    INDEX_DIR.mkdir(exist_ok=True)
    faiss.write_index(index, str(INDEX_DIR / "faiss.index"))
    with open(INDEX_DIR / "chunks.jsonl", "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c) + "\n")
    (INDEX_DIR / "meta.json").write_text(json.dumps(
        {"embedder": args.embedder, "dim": int(vecs.shape[1]), "n_chunks": len(chunks)}))
    print(f"Index saved to {INDEX_DIR} (embedder={args.embedder})")


if __name__ == "__main__":
    main()
