"""Central settings. Change models/prices here only."""
import os

# Models are tried in this order; if one is overloaded (503/timeout) or not
# available (404) the next is used automatically. Override with:
#   export GEN_MODEL=some-model-name      (uses only that model)
_env = os.environ.get("GEN_MODEL")
GEN_MODELS = [_env] if _env else [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.7-flash",
    "gemini-3.8-flash",
]
GEN_MODEL = GEN_MODELS[0]

# Prices in USD per 1M tokens, used ONLY for the cost note. Check Google's
# current Gemini API pricing page for the model you actually used.
PRICE_IN_PER_M = 0.30
PRICE_OUT_PER_M = 2.50

TOP_K = 4              # chunks sent to the LLM
POOL = 12              # candidates from each retriever before fusion
RRF_K = 60             # reciprocal-rank-fusion constant
