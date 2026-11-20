"""Offline tests: no API key needed. Run: python tests/test_offline.py"""
import json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from guardrails import screen_input, redact_output

def test_guardrails():
    r = screen_input("Customer card 4111 1111 1111 1111 cvv 123 wants refund")
    assert r["blocked"] and "card" in r["found"] and "4111" not in r["text"]
    r = screen_input("Call 9876543210 or mail a.b@x.com about order 1234")
    assert not r["blocked"] and "9876543210" not in r["text"] and "a.b@x.com" not in r["text"]
    assert "order 1234" in r["text"]
    assert "[AADHAAR]" in screen_input("aadhaar 1234 5678 9012")["text"]
    assert not screen_input("Order 4111 is late")["found"]           # not a card (Luhn)
    assert "9876543210" not in redact_output("Ring 9876543210")

def test_retrieval_prefers_latest():
    subprocess.run([sys.executable, str(ROOT / "src/ingest.py"), "--embedder", "hash"],
                   check=True, capture_output=True)
    from retrieve import Retriever
    r = Retriever()
    ids = lambda q: [c["chunk_id"] for c in r.search(q, k=4)]
    top = ids("laptop warranty period months")
    assert "WAR-001_v2#0" in top and "WAR-001_v1#0" not in top, top
    top = ids("same day delivery Indore before 2 PM")
    assert "DEL-001_v2#0" in top and "DEL-001_v1#0" not in top, top
    old = [c["chunk_id"] for c in r.search("laptop warranty", k=8, include_old=True)]
    assert "WAR-001_v1#0" in old

def test_ask_with_mock_llm():
    import llm, answer
    def fake(system, prompt, retries=5):
        cid = prompt.split("chunk_id=")[1].split(" ")[0]
        return {"status": "answered", "answer": "10 days. Call 9876543210.", "citations": [cid, "FAKE#9"]}, (900, 60)
    llm.generate_json = fake
    r = answer.ask("How long to return electronics?", use_rerank=False)
    assert r["status"] == "answered" and len(r["citations"]) == 1       # fake id dropped
    assert "9876543210" not in r["answer"] and r["cost_usd"] > 0
    llm.generate_json = lambda s, p, retries=5: ({"status": "answered", "answer": "x", "citations": []}, (1, 1))
    assert answer.ask("anything about returns", use_rerank=False)["status"] == "unknown"  # uncited -> unknown
    r = answer.ask("My card 4111111111111111 cvv 123, refund?", use_rerank=False)
    assert r["status"] == "blocked"

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("PASS", name)
