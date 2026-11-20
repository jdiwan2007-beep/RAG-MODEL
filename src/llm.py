"""Thin wrapper around Gemini with model fallback, timeouts and clear errors."""
import json
import os
import sys
import time

from config import GEN_MODELS

LAST_MODEL = None     # which model produced the latest answer (for the cost note)
_STAGE = {}           # remembers which request options each model accepts


def _client():
    from google import genai
    from google.genai import types
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"],
                        http_options=types.HttpOptions(timeout=60000))  # 60 s


def generate_json(system: str, prompt: str, retries: int = 2):
    """Return (parsed_json, (tokens_in, tokens_out)).

    Per model: temporary problems (503/429/timeout) are retried, then the next
    model is tried. A 404 skips to the next model. A 400 steps down to simpler
    request settings and remembers the result so later calls don't repeat it.
    Bad key (401/403) fails immediately with a clear message.
    """
    global LAST_MODEL
    from google.genai import types
    client = _client()

    def make_cfg(stage):
        # stage 0: all options; 1: no thinking option; 2: also no temperature
        kw = dict(system_instruction=system, response_mime_type="application/json")
        if stage < 2:
            kw["temperature"] = 0
        if stage == 0:
            kw["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
        return types.GenerateContentConfig(**kw)

    problems = []
    for model in GEN_MODELS:
        stage = _STAGE.get(model, 0)
        attempt = 0
        while attempt < retries:
            try:
                resp = client.models.generate_content(
                    model=model, contents=prompt, config=make_cfg(stage))
                _STAGE[model] = stage
                u = resp.usage_metadata
                toks = (u.prompt_token_count or 0,
                        (u.candidates_token_count or 0)
                        + (getattr(u, "thoughts_token_count", 0) or 0))
                data = json.loads(resp.text)
                LAST_MODEL = model
                return data, toks
            except json.JSONDecodeError:
                print(f"  ({model}: invalid JSON, retrying)", file=sys.stderr)
                attempt += 1
            except Exception as e:
                code = getattr(e, "code", None)
                msg = str(e)[:200]
                if code == 400 and stage < 2:
                    stage += 1
                    print(f"  {model}: rejected options, retrying with simpler settings",
                          file=sys.stderr)
                    continue
                if code == 404:
                    problems.append(f"{model}: not available (404)")
                    print(f"  {model} not available, trying next model", file=sys.stderr)
                    break
                if code in (400, 401, 403):
                    raise RuntimeError(f"Gemini rejected the request (code {code}): {msg}") from e
                attempt += 1                     # 429 / 5xx / timeout
                problems.append(f"{model}: {code or 'timeout'}")
                if attempt < retries:
                    wait = 5 * attempt
                    print(f"  {model} busy (code {code}); retrying in {wait}s", file=sys.stderr)
                    time.sleep(wait)
                else:
                    print(f"  {model} still busy, trying next model", file=sys.stderr)
    raise RuntimeError("All Gemini models failed: " + "; ".join(problems[-6:]))
