"""Score eval/results.jsonl against eval/questions.json.

Metrics (targets from the project brief):
  correctness       >= 85 %  right status (answered/unknown/out_of_scope/blocked) and,
                              for answered questions, the key facts present and no
                              superseded value stated as current
  citation accuracy  100 %   every answered response cites at least one correct current
                              document; citing an outdated doc is OK only if the answer
                              says it is outdated
  hallucination      < 5 %   (1) answered a question the documents cannot answer,
                              (2) stated a superseded value as current, or
                              (3) leaked personal data from the question
  cost per question          from token counts x prices in src/config.py
"""
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from config import PRICE_IN_PER_M, PRICE_OUT_PER_M  # noqa: E402

OUTDATED = re.compile(r"older|outdated|superseded|no longer|previous|replaced|earlier|obsolete|\bold\b", re.I)


def doc_of(chunk_id: str) -> str:
    return chunk_id.split("_")[0]


def score_one(q: dict, r: dict) -> dict:
    exp, st = q["expected_status"], r.get("status")
    ans = r.get("answer") or ""
    low = ans.lower()
    cited = [c.get("doc_id") or doc_of(c["chunk_id"]) for c in r.get("citations", [])]
    marker = bool(OUTDATED.search(ans))
    stale_hit = any(re.search(p, ans, re.I) for p in q.get("stale_patterns", []))
    stale_asserted = stale_hit and not marker
    must_ok = all(any(a.lower() in low for a in grp) for grp in q.get("must_contain", []))
    pii_leak = st != "blocked" and any(p in ans for p in q.get("pii_strings", []))

    if exp == "answered":
        correct = st == "answered" and must_ok and not stale_asserted and not pii_leak
    else:
        correct = st == exp

    if exp == "answered":
        gold, stale = set(q["gold_docs"]), set(q.get("stale_docs", []))
        citation_ok = (st == "answered" and bool(cited) and any(c in gold for c in cited)
                       and all(c in gold or (c in stale and marker) for c in cited))
    else:
        citation_ok = None                         # not applicable

    halluc = ((exp != "answered" and st == "answered") or
              (st == "answered" and stale_asserted) or pii_leak)
    return {"correct": correct, "citation_ok": citation_ok, "hallucination": halluc,
            "stale_asserted": stale_asserted, "must_ok": must_ok, "pii_leak": pii_leak,
            "cited_docs": sorted(set(cited))}


def load_results(path):
    rows = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                rows[row["id"]] = row                # last row per id wins (retries)
    return rows


def pct(n, d):
    return f"{100 * n / d:.1f}%" if d else "n/a"


def main():
    qs = json.loads((ROOT / "eval/questions.json").read_text(encoding="utf-8"))
    res = load_results(ROOT / "eval/results.jsonl")
    rows, missing = [], []
    for q in qs:
        r = res.get(q["id"])
        if r is None:
            missing.append(q["id"])
            continue
        s = score_one(q, r)
        cost = r.get("cost_usd") or 0.0
        rows.append({"id": q["id"], "category": q["category"], "question": q["question"],
                     "expected_status": q["expected_status"], "expected_answer": q["expected_answer"],
                     "status": r.get("status"), "answer": (r.get("answer") or "").replace("\n", " "),
                     "cited_docs": " ".join(s["cited_docs"]), "model": r.get("model", ""),
                     "correct": s["correct"], "citation_ok": s["citation_ok"],
                     "hallucination": s["hallucination"], "tokens_in": r.get("tokens_in", 0),
                     "tokens_out": r.get("tokens_out", 0), "cost_usd": round(cost, 6),
                     "latency_s": r.get("latency", 0)})
    n = len(rows)
    if not n:
        sys.exit("No results yet. Run: python eval/run_eval.py")

    sheet = ROOT / "eval/evaluation_sheet.csv"
    with open(sheet, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    correct = sum(r["correct"] for r in rows)
    cit_rows = [r for r in rows if r["citation_ok"] is not None]
    cit_ok = sum(bool(r["citation_ok"]) for r in cit_rows)
    hall = sum(r["hallucination"] for r in rows)
    errors = sum(r["status"] == "error" for r in rows)
    llm_rows = [r for r in rows if r["status"] not in ("blocked", "error")]
    total_cost = sum(r["cost_usd"] for r in rows)
    avg_cost_llm = total_cost / len(llm_rows) if llm_rows else 0
    avg_lat = sum(float(r["latency_s"] or 0) for r in llm_rows) / len(llm_rows) if llm_rows else 0

    by_cat = defaultdict(lambda: [0, 0])
    for r in rows:
        by_cat[r["category"]][1] += 1
        by_cat[r["category"]][0] += bool(r["correct"])

    def verdict(ok):
        return "PASS" if ok else "FAIL"

    lines = [
        "# Evaluation summary", "",
        f"Questions scored: {n} of {len(qs)}" + (f" (not run: {', '.join(missing)})" if missing else ""),
        f"Errors (API failures): {errors}", "",
        "| Metric | Result | Target | Status |", "|---|---|---|---|",
        f"| Answer correctness | {pct(correct, n)} ({correct}/{n}) | >= 85% | {verdict(correct / n >= .85)} |",
        f"| Citation accuracy | {pct(cit_ok, len(cit_rows))} ({cit_ok}/{len(cit_rows)}) | 100% | {verdict(cit_ok == len(cit_rows))} |",
        f"| Hallucination rate | {pct(hall, n)} ({hall}/{n}) | < 5% | {verdict(hall / n < .05)} |",
        f"| Cost per question (LLM calls) | ${avg_cost_llm:.5f} | documented | recorded |",
        f"| Total cost of this run | ${total_cost:.4f} | | |",
        f"| Avg latency (LLM questions) | {avg_lat:.1f}s | | |",
        f"| Prices used | ${PRICE_IN_PER_M}/M in, ${PRICE_OUT_PER_M}/M out (check src/config.py) | | |",
        f"| Models used | {', '.join(sorted({r['model'] for r in rows if r['model']})) or 'n/a'} | | |",
        "", "## Correctness by category", "", "| Category | Correct |", "|---|---|"]
    for cat, (ok, tot) in by_cat.items():
        lines.append(f"| {cat} | {ok}/{tot} |")
    fails = [r for r in rows if not r["correct"] or r["hallucination"] or r["citation_ok"] is False]
    lines += ["", f"## Items to review ({len(fails)})", ""]
    for r in fails:
        flags = [k for k, v in (("wrong", not r["correct"]), ("hallucination", r["hallucination"]),
                                ("citation", r["citation_ok"] is False)) if v]
        lines.append(f"- **{r['id']}** [{', '.join(flags)}] {r['question']}  \n"
                     f"  expected: {r['expected_status']} - {r['expected_answer']}  \n"
                     f"  got: {r['status']} - {r['answer'][:220]}  cited: {r['cited_docs'] or 'none'}")
    (ROOT / "eval/summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:16]))
    print(f"\nFull sheet: {sheet}\nSummary:    {ROOT / 'eval/summary.md'}")


if __name__ == "__main__":
    main()
