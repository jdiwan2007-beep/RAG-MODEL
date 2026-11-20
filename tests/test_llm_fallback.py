"""Offline tests of Gemini fallback logic (fake client). Run: python tests/test_llm_fallback.py"""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'src'))
import types as T, json, llm
class Err(Exception):
    def __init__(s,code,msg="x"): super().__init__(msg); s.code=code
class Resp:
    def __init__(s,t): s.text=t; s.usage_metadata=T.SimpleNamespace(prompt_token_count=10,candidates_token_count=5,thoughts_token_count=0)
calls=[]
class Models:
    def __init__(s,plan): s.plan=plan
    def generate_content(s,model,contents,config):
        calls.append(model); r=s.plan[model]
        if isinstance(r,Exception): raise r
        return Resp(r)
def run(plan, models):
    calls.clear(); llm._STAGE.clear(); llm.GEN_MODELS=models; llm.time.sleep=lambda s:None
    llm._client=lambda: T.SimpleNamespace(models=Models(plan))
    return llm.generate_json("s","p")
# 404 -> next model
d,t=run({"a":Err(404),"b":'{"ok":1}'},["a","b"]); assert d=={"ok":1} and calls==["a","b"] and llm.LAST_MODEL=="b"
# 503 twice -> next model
d,t=run({"a":Err(503),"b":'{"ok":2}'},["a","b"]); assert calls==["a","a","b"]
# thinking rejected -> retry same model
n={"c":0}
class M2(Models):
    def generate_content(s,model,contents,config):
        calls.append(model)
        if getattr(config,"thinking_config",None) is not None: raise Err(400,"thinking not supported")
        return Resp('{"ok":3}')
calls.clear(); llm._STAGE.clear(); llm.GEN_MODELS=["a"]; llm._client=lambda: T.SimpleNamespace(models=M2({}))
assert llm.generate_json("s","p")[0]=={"ok":3} and calls==["a","a"]
# bad key fails fast
try: run({"a":Err(403,"bad key"),"b":'{}'},["a","b"]); assert False
except RuntimeError as e: assert "403" in str(e) and calls==["a"]
# everything down
try: run({"a":Err(503),"b":Err(404)},["a","b"]); assert False
except RuntimeError as e: assert "All Gemini models failed" in str(e)
print("fallback tests PASS")

# generic 400 (no mention of thinking) -> steps down to simpler settings
class M3(Models):
    def generate_content(s,model,contents,config):
        calls.append(model)
        if getattr(config,"thinking_config",None) is not None: raise Err(400,"Request contains an invalid argument.")
        return Resp('{"ok":4}')
calls.clear(); llm._STAGE.clear(); llm.GEN_MODELS=["a"]; llm._client=lambda: T.SimpleNamespace(models=M3({}))
assert llm.generate_json("s","p")[0]=={"ok":4} and calls==["a","a"]
# 400 until temperature also removed
class M4(Models):
    def generate_content(s,model,contents,config):
        calls.append(model)
        if config.temperature is not None: raise Err(400,"Request contains an invalid argument.")
        return Resp('{"ok":5}')
calls.clear(); llm._STAGE.clear(); llm._client=lambda: T.SimpleNamespace(models=M4({}))
assert llm.generate_json("s","p")[0]=={"ok":5} and calls==["a","a","a"]
# 400 that never goes away -> fails with clear error after 3 stages
class M5(Models):
    def generate_content(s,model,contents,config): calls.append(model); raise Err(400,"bad")
calls.clear(); llm._STAGE.clear(); llm._client=lambda: T.SimpleNamespace(models=M5({}))
try: llm.generate_json("s","p"); assert False
except RuntimeError as e: assert "400" in str(e) and len(calls)==3
print("400-stepdown tests PASS")

# stage is remembered: second call must NOT repeat the failed attempts
llm._STAGE.clear()
class M6(Models):
    def generate_content(s,model,contents,config):
        calls.append(model)
        if config.temperature is not None: raise Err(400,"Request contains an invalid argument.")
        return Resp('{"ok":6}')
calls.clear(); llm._STAGE.clear(); llm.GEN_MODELS=["z"]; llm._client=lambda: T.SimpleNamespace(models=M6({}))
llm.generate_json("s","p"); assert len(calls)==3
calls.clear(); llm.generate_json("s","p"); assert len(calls)==1, calls
print("stage-memory test PASS")
