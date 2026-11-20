"""RAG answering: guardrails -> retrieve -> Gemini (cited, may say 'I don't know')."""
import sys
import time

from config import PRICE_IN_PER_M, PRICE_OUT_PER_M, TOP_K
from guardrails import redact_output, screen_input
import llm
from retrieve import Retriever, llm_rerank

SYSTEM = """You are the internal knowledge assistant for ElectroMart Indore, an electronics e-commerce store.
Answer staff questions using ONLY the numbered sources provided.

Rules:
1. Every factual claim must come from the sources. Never use outside knowledge or guess.
2. If the sources do not contain the answer, set status to "unknown" and say you could not find it in the documents.
3. If the question is not about ElectroMart's policies, products, orders, payments, delivery, warranty or support
   (for example general knowledge, coding, medical or legal advice, opinions), set status to "out_of_scope".
4. If sources conflict, trust the one with the LATEST effective date and say briefly that an older document differs.
5. Never reveal or ask for personal data (phone, address, Aadhaar, card details).
6. Be concise: 1 to 4 sentences, or a short list for steps.

Return JSON only:
{"status": "answered" | "unknown" | "out_of_scope",
 "answer": "text for the staff member",
 "citations": ["chunk_id", ...]}   // only chunk_ids you actually used"""

_retriever = None


def get_retriever():
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever


def format_sources(chunks):
    return "\n\n".join(
        f"SOURCE chunk_id={c['chunk_id']} | {c['title']} ({c['doc_id']} {c['version']}, "
        f"effective {c['effective_date']}, {c['department']})\n{c['text']}" for c in chunks)


def ask(question: str, use_rerank: bool = True) -> dict:
    t0 = time.time()
    screened = screen_input(question)
    base = {"question": question, "notices": [], "citations": [], "tokens_in": 0,
            "tokens_out": 0, "cost_usd": 0.0}
    if screened["blocked"]:
        return dict(base, status="blocked", answer=screened["message"],
                    latency=round(time.time() - t0, 2))
    if screened["found"]:
        base["notices"].append("Personal data in your question was redacted before processing: "
                               + ", ".join(sorted(set(screened["found"]))))
    q = screened["text"]

    chunks = get_retriever().search(q, k=TOP_K, rerank_fn=llm_rerank if use_rerank else None)
    data, (tin, tout) = llm.generate_json(SYSTEM, f"{format_sources(chunks)}\n\nQUESTION: {q}")

    by_id = {c["chunk_id"]: c for c in chunks}
    cites = [by_id[c] for c in dict.fromkeys(data.get("citations", [])) if c in by_id]
    status = data.get("status", "unknown")
    if status not in ("answered", "unknown", "out_of_scope"):
        status = "unknown"
    answer = redact_output(str(data.get("answer", "")))
    if status == "answered" and not cites:            # uncited answers are not allowed
        status, answer = "unknown", "I couldn't find a documented answer to that, so I won't guess."
    if status != "answered":
        cites = []
    return dict(base, status=status, answer=answer, citations=cites,
                retrieved=[c["chunk_id"] for c in chunks], tokens_in=tin, tokens_out=tout,
                cost_usd=(tin * PRICE_IN_PER_M + tout * PRICE_OUT_PER_M) / 1e6,
                latency=round(time.time() - t0, 2))


if __name__ == "__main__":
    r = ask(" ".join(sys.argv[1:]) or "How long do I have to return a laptop?")
    print(f"[{r['status']}] {r['answer']}")
    for c in r["citations"]:
        print(f"  - {c['title']} ({c['doc_id']} {c['version']})")
    for n in r["notices"]:
        print("  note:", n)
    print(f"  tokens {r['tokens_in']}/{r['tokens_out']}  cost ${r['cost_usd']:.5f}  {r['latency']}s")
