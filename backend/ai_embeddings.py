"""Text embeddings for the Business Brain RAG.

Strategy:
- Primary: local ONNX embedding via fastembed (BAAI/bge-small-en-v1.5, 384 dims,
  CPU-only, no torch). Works with any GROQ key plan.
- Optional: if GROQ_API_KEY exposes an embedding model (set via GROQ_EMBED_MODEL
  env var or discovered at runtime), GROQ embeddings are used instead.

The embedding provider is detected once at import time and cached.
"""

import os
import math
import logging

logger = logging.getLogger(__name__)

_GROQ_EMBED_MODEL = os.environ.get("GROQ_EMBED_MODEL", "").strip()
_LOCAL_MODEL = "BAAI/bge-small-en-v1.5"
_provider = None
_embedding_fn = None


def _detect_groq_embed_model():
    """If a GROQ key is configured, check whether it can serve embeddings."""
    if not os.environ.get("GROQ_API_KEY"):
        return ""
    model = _GROQ_EMBED_MODEL or "nomic-embed-text"
    try:
        from groq import Groq
        client = Groq()
        resp = client.models.list().data
        ids = [m.id for m in resp]
        # Prefer requested model if available; else first embed model.
        if model in ids:
            return model
        for mid in ids:
            if "embed" in mid.lower():
                return mid
    except Exception as e:
        logger.warning(f"groq embed detection failed: {e}")
    return ""


class _LocalEmbedder:
    def __init__(self, model_name: str):
        from fastembed import TextEmbedding
        self.fe = TextEmbedding(model_name=model_name)
        self.dim = 384

    def embed(self, texts: list) -> list:
        if not texts:
            return []
        try:
            return [list(v) for v in self.fe.embed(list(texts))]
        except Exception as e:
            logger.error(f"local embedding failed: {e}")
            return []


class _GroqEmbedder:
    def __init__(self, model_name: str):
        from groq import AsyncGroq
        self.model = model_name
        self.groq = AsyncGroq()
        self.dim = None  # unknown until first call

    async def embed(self, texts: list) -> list:
        if not texts:
            return []
        try:
            resp = await self.groq.embeddings.create(model=self.model, input=list(texts))
            out = []
            for item in resp.data:
                v = item.embedding
                if self.dim is None:
                    self.dim = len(v)
                out.append(list(v))
            return out
        except Exception as e:
            logger.error(f"groq embedding failed: {e}")
            return []


def _init():
    global _provider, _embedding_fn
    gm = _detect_groq_embed_model()
    if gm:
        _provider = "groq"
        _embedding_fn = _GroqEmbedder(gm).embed
        logger.info(f"embeddings: groq://{gm}")
    else:
        try:
            emb = _LocalEmbedder(_LOCAL_MODEL)
            _provider = "local"
            _embedding_fn = emb.embed
            logger.info(f"embeddings: local://{_LOCAL_MODEL} (dim {emb.dim})")
        except Exception as e:
            logger.error(f"embeddings unavailable: {e}")
            _provider = None


_init()


def embed(texts: list) -> list:
    """Synchronous embedding (local provider). Returns list of float vectors.
    For the groq provider, use embed_async() instead."""
    if _embedding_fn is None or _provider != "local":
        return []
    return _embedding_fn(list(texts))


async def embed_async(texts: list) -> list:
    """Async embedding. If the provider is synchronous (local), runs in thread."""
    if _embedding_fn is None:
        return []
    if _provider == "groq":
        return await _embedding_fn(texts)
    import asyncio
    return await asyncio.to_thread(lambda: _embedding_fn(list(texts)))


def _to_floats(v):
    try:
        return [float(x) for x in v]
    except (TypeError, ValueError):
        return []


def cosine(a, b) -> float:
    a = _to_floats(a)
    b = _to_floats(b)
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


def provider_info() -> dict:
    return {"provider": _provider or "none"}
