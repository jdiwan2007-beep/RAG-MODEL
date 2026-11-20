"""Offline checks of the evaluation set and scorer. Run: python tests/test_eval_offline.py"""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "eval"))
from guardrails import screen_input
from score import score_one

QS = json.loads((ROOT / "eval/questions.json").read_text(encoding="utf-8"))
truth = json.loads((ROOT / "data/ground_truth.json").read_text())

def current_text():
    latest = {}
    for t in truth:
        if t["doc_id"] not in latest or t["effective_date"] > latest[t["doc_id"]]["effective_date"]:
            latest[t["doc_id"]] = t
    return {d: (ROOT / "data/raw" / t["file"]).read_text().lower() for d, t in latest.items()}

def test_set_shape():
    assert len(QS) == 60 and len({q["id"] for q in QS}) == 60
    from collections import Counter
    c = Counter(q["expected_status"] for q in QS)
    assert c == {"answered": 43, "unknown": 7, "out_of_scope": 6, "blocked": 4}, c

def test_expectations_match_documents():
    txt = current_text()
    for q in QS:
        if q["expected_status"] != "answered":
            continue
        for d in q["gold_docs"]:
            assert d in txt, (q["id"], d)
        gold_text = " ".join(txt[d] for d in q["gold_docs"])
        for grp in q["must_contain"]:
            assert any(a.lower() in gold_text for a in grp), (q["id"], grp)

def test_guardrails_on_eval_questions():
    for q in QS:
        r = screen_input(q["question"])
        if q["expected_status"] == "blocked":
            assert r["blocked"], q["id"]
        else:
            assert not r["blocked"], q["id"]
        for p in q["pii_strings"]:
            assert p not in r["text"], (q["id"], p)

def fake(status, answer, docs):
    return {"status": status, "answer": answer,
            "citations": [{"chunk_id": f"{d}_v1#0", "doc_id": d} for d in docs]}

def test_scorer():
    q = {x["id"]: x for x in QS}
    r = score_one(q["Q01"], fake("answered", "Electronics can be returned within 10 days.", ["RET-001"]))
    assert r["correct"] and r["citation_ok"] and not r["hallucination"]
    # stale value stated as current -> wrong + hallucination
    r = score_one(q["Q01"], fake("answered", "You have 10 days, or 7 days per policy.", ["RET-001"]))
    assert not r["correct"] and r["hallucination"]
    # stale value mentioned but flagged as outdated; citing the old FAQ is allowed
    r = score_one(q["Q01"], fake("answered", "10 days. An older FAQ says 7 days, which is outdated.", ["RET-001", "RET-005"]))
    assert r["correct"] and r["citation_ok"] and not r["hallucination"]
    # citing the stale doc WITHOUT saying it is outdated -> citation fail
    r = score_one(q["Q01"], fake("answered", "10 days.", ["RET-001", "RET-005"]))
    assert r["citation_ok"] is False
    # answered without any citation
    r = score_one(q["Q01"], fake("answered", "10 days.", []))
    assert r["citation_ok"] is False
    # unknown question answered anyway -> hallucination
    unk = next(x for x in QS if x["expected_status"] == "unknown")
    r = score_one(unk, fake("answered", "Yes, 10% off.", ["SUP-005"]))
    assert r["hallucination"] and not r["correct"]
    assert score_one(unk, fake("unknown", "I could not find that.", []))["correct"]
    # pii leak
    pii = next(x for x in QS if x["category"] == "pii")
    r = score_one(pii, fake("answered", "Call 9876543210: 2 working days.", ["RET-004"]))
    assert r["pii_leak"] and r["hallucination"]
    # EMI regex must not trip on Rs 15,000
    r = score_one(q["Q23"] if q["Q23"]["question"].startswith("What is the minimum purchase") else
                  next(x for x in QS if "no-cost EMI" in x["question"]),
                  fake("answered", "Rs 10,000 for credit cards; debit card EMI above Rs 15,000.", ["PAY-002"]))
    assert r["correct"], r

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("PASS", name)
