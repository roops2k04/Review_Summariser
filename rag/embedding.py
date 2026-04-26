import os

# Reduce noisy logs/warnings from HuggingFace + Transformers.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

import io
import threading
from contextlib import redirect_stderr, redirect_stdout
from functools import lru_cache

try:
    from huggingface_hub.utils import logging as hf_logging

    hf_logging.set_verbosity_error()
except Exception:
    pass

try:
    from transformers.utils import logging as tf_logging

    tf_logging.set_verbosity_error()
except Exception:
    pass

from sentence_transformers import SentenceTransformer

_MODEL_LOCK = threading.Lock()


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    # Sentence-Transformers/Transformers can print noisy reports (e.g. UNEXPECTED keys)
    # and HF Hub warnings to stdout/stderr during first load. Suppress them.
    with _MODEL_LOCK:
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            return SentenceTransformer(model_name)


def _to_list(v):
    # sentence-transformers returns numpy arrays; Chroma expects plain Python lists.
    try:
        return v.tolist()
    except Exception:
        return list(v)


def embed_texts(texts):
    texts = [t if isinstance(t, str) else "" for t in (texts or [])]
    if not texts:
        return []

    model = _get_model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [_to_list(v) for v in vectors]


def embed_query(query):
    query = query if isinstance(query, str) else ""
    model = _get_model()
    vector = model.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]
    return _to_list(vector)
