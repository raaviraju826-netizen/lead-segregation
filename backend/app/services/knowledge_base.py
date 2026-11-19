from __future__ import annotations

import hashlib
import logging
import math
import threading

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    HAS_CHROMA = True
except Exception:
    chromadb = None
    ChromaSettings = None
    HAS_CHROMA = False

from ..config import CONFIG_DIR, get_settings
from .embeddings import get_embedder
from .taxonomy import load_taxonomy

log = logging.getLogger(__name__)
_lock = threading.Lock()
_client = None
_kb = None
_examples = None
TOP_K = 8


class _InMemoryCollection:
    def __init__(self, name: str):
        self.name = name
        self._items: dict[str, tuple[str, list[float], dict]] = {}

    def count(self) -> int:
        return len(self._items)

    def add(self, ids: list[str], documents: list[str], embeddings: list[list[float]], metadatas: list[dict]):
        self.upsert(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)

    def upsert(self, ids: list[str], documents: list[str], embeddings: list[list[float]], metadatas: list[dict]):
        for cid, doc, emb, meta in zip(ids, documents, embeddings, metadatas):
            self._items[cid] = (doc, emb, meta)

    def delete(self, ids: list[str]):
        for cid in ids:
            self._items.pop(cid, None)

    def query(self, query_embeddings: list[list[float]], n_results: int = 8, include: list[str] | None = None) -> dict:
        if not query_embeddings or not self._items:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        q = query_embeddings[0]
        qn = math.sqrt(sum(x * x for x in q)) or 1.0
        scored = []
        for cid, (doc, emb, meta) in self._items.items():
            en = math.sqrt(sum(x * x for x in emb)) or 1.0
            cos = sum(a * b for a, b in zip(q, emb)) / (qn * en)
            dist = max(0.0, 1.0 - cos)
            scored.append((dist, cid, doc, meta))
        scored.sort(key=lambda t: t[0])
        top = scored[:max(1, n_results)]
        return {
            "ids": [[t[1] for t in top]],
            "documents": [[t[2] for t in top]],
            "metadatas": [[t[3] for t in top]],
            "distances": [[t[0] for t in top]],
        }


class _InMemoryClient:
    def __init__(self):
        self._cols: dict[str, _InMemoryCollection] = {}

    def list_collections(self):
        return list(self._cols.values())

    def delete_collection(self, name: str):
        self._cols.pop(name, None)

    def get_or_create_collection(self, name: str, metadata: dict | None = None):
        if name not in self._cols:
            self._cols[name] = _InMemoryCollection(name)
        return self._cols[name]

    def create_collection(self, name: str, metadata: dict | None = None):
        self._cols[name] = _InMemoryCollection(name)
        return self._cols[name]


def _chroma():
    global _client
    if _client is None:
        if HAS_CHROMA:
            try:
                _client = chromadb.PersistentClient(path=get_settings().chroma_dir, settings=ChromaSettings(anonymized_telemetry=False))
            except Exception:
                _client = _InMemoryClient()
        else:
            _client = _InMemoryClient()
    return _client


def build_chunks() -> list[dict]:
    chunks: list[dict] = []
    for ind in load_taxonomy()["industries"]:
        subs = ", ".join(ind["sub_industries"].keys())
        chunks.append({
            "id": f"{ind['slug']}::overview", "industry": ind["name"], "sub_industry": "",
            "text": f"Industry: {ind['name']}. {ind['description'].strip()} Keywords: {', '.join(ind['keywords'])}. Sub-industries: {subs}.",
        })
        chunks.append({
            "id": f"{ind['slug']}::examples", "industry": ind["name"], "sub_industry": "",
            "text": f"Industry: {ind['name']}. Example businesses: {', '.join(ind['example_businesses'])}. "
                    f"Disambiguation: {ind['disambiguation'].strip()}",
        })
        for sub, meta in ind["sub_industries"].items():
            chunks.append({
                "id": f"{ind['slug']}::{sub.lower().replace(' ', '-')}", "industry": ind["name"], "sub_industry": sub,
                "text": f"Industry: {ind['name']}. Sub-industry: {sub}. Keywords: {', '.join(meta['keywords'])}.",
            })
    return chunks


def ensure_knowledge_base(example_rows: list[tuple[int, str, str, str | None]] | None = None) -> int:
    """(Re)build the vector KB from industries.yaml when the taxonomy or embedder changed. Returns chunk count."""
    global _kb, _examples
    with _lock:
        emb = get_embedder()
        chunks = build_chunks()
        if hasattr(emb, "fit"):
            emb.fit([c["text"] for c in chunks])
        digest = hashlib.sha256((CONFIG_DIR / "industries.yaml").read_bytes() + emb.provider.encode()).hexdigest()[:10]
        name = f"industry_kb_{emb.provider}_{digest}"
        client = _chroma()
        for c in client.list_collections():
            cname = getattr(c, "name", c)
            if cname.startswith("industry_kb_") and cname != name:
                client.delete_collection(cname)
        _kb = client.get_or_create_collection(name, metadata={"hnsw:space": "cosine"})
        if _kb.count() != len(chunks):
            if _kb.count():
                client.delete_collection(name)
                _kb = client.create_collection(name, metadata={"hnsw:space": "cosine"})
            _kb.add(
                ids=[c["id"] for c in chunks], documents=[c["text"] for c in chunks],
                embeddings=emb.embed([c["text"] for c in chunks]),
                metadatas=[{"industry": c["industry"], "sub_industry": c["sub_industry"]} for c in chunks],
            )
            log.info("Built industry knowledge base %s with %d chunks", name, len(chunks))
        ex_name = f"review_examples_{emb.provider}_{digest}"
        for c in client.list_collections():
            cname = getattr(c, "name", c)
            if cname.startswith("review_examples_") and cname != ex_name and example_rows is None:
                pass  # stale example collections are rebuilt from the database by the caller
        _examples = client.get_or_create_collection(ex_name, metadata={"hnsw:space": "cosine"})
        if example_rows and _examples.count() == 0:
            _examples.upsert(
                ids=[f"review-{r[0]}" for r in example_rows], documents=[r[1][:800] for r in example_rows],
                embeddings=emb.embed([r[1][:800] for r in example_rows]),
                metadatas=[{"industry": r[2], "sub_industry": r[3] or ""} for r in example_rows])
        return len(chunks)


def _to_hits(res: dict) -> list[dict]:
    hits = []
    emb = get_embedder()
    if not res.get("ids") or not res["ids"][0]:
        return hits
    for i, cid in enumerate(res["ids"][0]):
        raw = max(0.0, 1.0 - float(res["distances"][0][i]))
        md = res["metadatas"][0][i]
        hits.append({
            "id": cid, "industry": md.get("industry"), "sub_industry": md.get("sub_industry") or None,
            "text": res["documents"][0][i], "raw_similarity": round(raw, 4),
            "similarity": round(min(1.0, raw / emb.sim_scale), 4),
        })
    return hits


def retrieve(query: str, k: int = TOP_K) -> list[dict]:
    if _kb is None:
        ensure_knowledge_base()
    emb = get_embedder()
    n = min(k, _kb.count())
    res = _kb.query(query_embeddings=emb.embed([query]), n_results=n, include=["documents", "metadatas", "distances"])
    return _to_hits(res)


def retrieve_examples(query: str, k: int = 2) -> list[dict]:
    if _examples is None:
        ensure_knowledge_base()
    if _examples.count() == 0:
        return []
    emb = get_embedder()
    res = _examples.query(query_embeddings=emb.embed([query]), n_results=min(k, _examples.count()),
                          include=["documents", "metadatas", "distances"])
    return _to_hits(res)


def add_reviewed_example(email_id: int, business_text: str, industry: str, sub_industry: str | None) -> None:
    """Called ONLY after a human reviewer confirms/corrects a classification."""
    if _examples is None:
        ensure_knowledge_base()
    emb = get_embedder()
    _examples.upsert(
        ids=[f"review-{email_id}"], documents=[business_text[:800]], embeddings=emb.embed([business_text[:800]]),
        metadatas=[{"industry": industry, "sub_industry": sub_industry or ""}],
    )


def remove_reviewed_example(email_id: int) -> None:
    if _examples is not None:
        try:
            _examples.delete(ids=[f"review-{email_id}"])
        except Exception:  # pragma: no cover
            pass


def kb_status() -> dict:
    emb = get_embedder()
    return {
        "embedding_provider": emb.provider,
        "chunks": _kb.count() if _kb else 0,
        "reviewed_examples": _examples.count() if _examples else 0,
    }
