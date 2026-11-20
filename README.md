# Retail GenAI Knowledge Assistant (ElectroMart Indore)

A retrieval-augmented generation (RAG) assistant that answers staff questions about a fictional
Indore electronics e-commerce store's policies, SOPs and FAQs, **with citations**, and says
"I don't know" when the documents don't cover the question.

## Pipeline
1. `src/generate_docs.py` creates 40 synthetic documents (returns, warranty, orders, payments,
   delivery, support) with deliberate duplicates, outdated versions and contradictions.
2. `src/ingest.py` extracts text, removes repeated headers/footers, converts tables to sentences,
   chunks with overlap, embeds (Gemini `gemini-embedding-001`) and stores vectors in FAISS with
   metadata (doc id, version, department, effective date).
3. `src/retrieve.py` hybrid search: BM25 + dense vectors, fused with reciprocal rank fusion, then
   re-ranked by the LLM. Older versions of a document are excluded (latest version wins).
4. `src/answer.py` generates a JSON answer (status, text, citations) using only retrieved sources.
   Answers without a valid citation are downgraded to "unknown". If sources conflict, the one with
   the latest effective date is trusted and the conflict is mentioned.
5. `src/guardrails.py` DPDP-style redaction of phone/email/Aadhaar/PAN in questions and answers;
   PCI-DSS-style blocking of card numbers (Luhn check), CVV and PIN before anything reaches the LLM.
6. `src/llm.py` Gemini wrapper with model fallback, timeouts and retries.

## Setup
    python3 -m venv venv && source venv/bin/activate
    pip install -r requirements.txt
    export GEMINI_API_KEY="your key from aistudio.google.com"   # never commit this
    python src/generate_docs.py      # optional: documents are already included
    python src/ingest.py             # builds index/
    python src/answer.py "How long do I have to return a laptop?"

## Evaluation (60 questions)
    python eval/run_eval.py          # about 15-20 min on the free tier; resumable
    python eval/score.py             # writes eval/evaluation_sheet.csv and eval/summary.md
Targets: correctness >= 85%, every answer cited correctly, hallucinations < 5%, cost per question documented.
Offline tests (no API key): `python tests/test_offline.py`, `tests/test_eval_offline.py`, `tests/test_llm_fallback.py`.

## Keeping answers fresh as documents change
Each chunk stores doc id, version and effective date. Re-run `python src/ingest.py` when documents
change (or on a schedule/file-watcher); retrieval only uses the latest version per doc id, and
conflicting older FAQs are flagged by date. Retire superseded files after a grace period.
