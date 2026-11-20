"""Run the 60 questions through the assistant and save eval/results.jsonl.

    python eval/run_eval.py                 # full run (about 15-20 minutes on the free tier)
    python eval/run_eval.py --limit 5       # quick trial
    python eval/run_eval.py --retry-errors  # re-run only questions that hit API errors

Safe to stop (Ctrl+C) and restart: finished questions are skipped.
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import answer  # noqa: E402
import llm  # noqa: E402

RESULTS = ROOT / "eval/results.jsonl"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sleep", type=float, default=6.0, help="seconds between questions")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--no-rerank", action="store_true")
    ap.add_argument("--retry-errors", action="store_true")
    args = ap.parse_args()

    qs = json.loads((ROOT / "eval/questions.json").read_text(encoding="utf-8"))
    last = {}
    if RESULTS.exists():
        for line in RESULTS.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                last[row["id"]] = row
    todo = [q for q in qs if q["id"] not in last or
            (args.retry_errors and last[q["id"]].get("status") == "error")]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(todo)} questions to run ({len(last)} already done)")

    for i, q in enumerate(todo, 1):
        try:
            r = answer.ask(q["question"], use_rerank=not args.no_rerank)
            if r["status"] != "blocked":
                r["model"] = llm.LAST_MODEL
        except Exception as e:                       # keep going; record the failure
            r = {"status": "error", "answer": f"{type(e).__name__}: {str(e)[:250]}",
                 "citations": [], "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "latency": 0}
        r["id"] = q["id"]
        r["citations"] = [{"chunk_id": c["chunk_id"], "doc_id": c["doc_id"],
                           "version": c["version"], "title": c["title"]}
                          for c in r.get("citations", [])]
        with open(RESULTS, "a", encoding="utf-8") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"[{i}/{len(todo)}] {q['id']} expected={q['expected_status']:<12} "
              f"got={r['status']:<12} {r.get('latency', 0)}s", flush=True)
        if r["status"] not in ("blocked",):
            time.sleep(args.sleep)
    print("Done. Now run: python eval/score.py")


if __name__ == "__main__":
    main()
