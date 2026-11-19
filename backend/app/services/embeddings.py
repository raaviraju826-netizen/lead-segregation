from __future__ import annotations

import logging
import math
import re
from typing import Protocol

from ..config import get_settings

log = logging.getLogger(__name__)

_STOP = set("a an the and or of to in for on with at by from is are was were be we our you your us it this that as i me my have has will can please".split())


def _stem(w: str) -> str:
    for suf in ("ing", "ers", "er", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            w = w[: -len(suf)]
            break
    return w[:-1] if w.endswith("e") and len(w) > 4 else w


def _tokens(text: str) -> list[str]:
    return [_stem(w) for w in re.findall(r"[a-z0-9&+#]+", text.lower()) if w not in _STOP and len(w) >= 2]


def _features(text: str) -> list[str]:
    toks = _tokens(text)
    return toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]


class Embedder(Protocol):
    provider: str
    sim_scale: float

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class KBTfidfEmbedder:
    """Offline, deterministic TF-IDF embedder fitted on the industry knowledge-base chunks themselves.

    Only terms that occur in the taxonomy are represented, so irrelevant words in an email (names, pleasantries) add no noise.
    It is a LEXICAL model, not a semantic one: it cannot relate synonyms that are absent from industries.yaml.
    Raw cosine values are modest, so `sim_scale` rescales them (documented in the README). Set EMBEDDING_PROVIDER=openai for neural embeddings.
    """

    provider = "local"
    sim_scale = 0.5

    def __init__(self) -> None:
        self.vocab: dict[str, int] = {}
        self.idf: list[float] = []

    def fit(self, texts: list[str]) -> None:
        df: dict[str, int] = {}
        for t in texts:
            for f in set(_features(t)):
                df[f] = df.get(f, 0) + 1
        self.vocab = {f: i for i, f in enumerate(sorted(df))}
        n = len(texts)
        self.idf = [math.log((1 + n) / (1 + df[f])) + 1.0 for f in sorted(df)]

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.vocab:
            raise RuntimeError("KBTfidfEmbedder must be fitted on the knowledge base first")
        out = []
        for t in texts:
            v = [0.0] * len(self.vocab)
            counts: dict[int, int] = {}
            for f in _features(t):
                i = self.vocab.get(f)
                if i is not None:
                    counts[i] = counts.get(i, 0) + 1
            for i, c in counts.items():
                v[i] = (1 + math.log(c)) * self.idf[i]
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
        return out


class OpenAIEmbedder:
    provider = "openai"
    sim_scale = 1.0

    def __init__(self) -> None:
        from openai import OpenAI

        s = get_settings()
        self.client = OpenAI(api_key=s.openai_api_key, base_url=s.openai_base_url or None)
        self.model = s.embedding_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        res = self.client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in res.data]


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        s = get_settings()
        if s.embedding_provider == "openai" and s.llm_enabled:
            _embedder = OpenAIEmbedder()
        else:
            if s.embedding_provider == "openai":
                log.warning("EMBEDDING_PROVIDER=openai but OPENAI_API_KEY is empty; using local TF-IDF embeddings")
            _embedder = KBTfidfEmbedder()
    return _embedder
