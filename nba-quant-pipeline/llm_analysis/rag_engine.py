"""
Lightweight RAG (Retrieval-Augmented Generation) engine.

Uses sentence-transformers for embeddings and FAISS for local vector search.
Stores/loads the index from disk so it persists across runs.

Typical workflow:
  1. Build index from historical events  (build_index / add_documents)
  2. Retrieve similar past events         (retrieve)
  3. Use retrieved context in LLM prompt  (retrieve_and_format)

The index file lives at LLM_ANALYSIS_INDEX_DIR (default: llm_analysis/.faiss_store/).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from dotenv import load_dotenv

load_dotenv()

_INDEX_DIR = Path(
    os.getenv("LLM_ANALYSIS_INDEX_DIR", Path(__file__).parent / ".faiss_store")
)
_EMBED_MODEL = os.getenv("LLM_ANALYSIS_EMBED_MODEL", "all-MiniLM-L6-v2")

_INDEX_FILE = _INDEX_DIR / "index.faiss"
_META_FILE = _INDEX_DIR / "metadata.json"

# Lazy-loaded singletons
_embedder = None
_faiss_index = None
_metadata: List[Dict] = []


def _get_embedder():
    """Lazy-load sentence-transformers model."""
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer(_EMBED_MODEL)
    return _embedder


def _embed(texts: List[str]) -> np.ndarray:
    model = _get_embedder()
    return model.encode(texts, normalize_embeddings=True, show_progress_bar=False)


def _ensure_index_dir():
    _INDEX_DIR.mkdir(parents=True, exist_ok=True)


def _load_index():
    """Load FAISS index + metadata from disk if they exist."""
    global _faiss_index, _metadata
    import faiss

    if _INDEX_FILE.exists() and _META_FILE.exists():
        _faiss_index = faiss.read_index(str(_INDEX_FILE))
        with open(_META_FILE) as f:
            _metadata = json.load(f)
    else:
        dim = _get_embedder().get_sentence_embedding_dimension()
        _faiss_index = faiss.IndexFlatIP(dim)
        _metadata = []


def _save_index():
    import faiss
    _ensure_index_dir()
    faiss.write_index(_faiss_index, str(_INDEX_FILE))
    with open(_META_FILE, "w") as f:
        json.dump(_metadata, f)


def _get_index():
    global _faiss_index
    if _faiss_index is None:
        _load_index()
    return _faiss_index


# ── Public API ──────────────────────────────────────────────────────────


def add_documents(texts: List[str], metadatas: Optional[List[Dict]] = None):
    """
    Embed texts and add them to the FAISS index.

    Args:
        texts: list of string descriptions (e.g. event summaries).
        metadatas: optional parallel list of dicts stored alongside each vector.
    """
    global _metadata
    idx = _get_index()
    vecs = _embed(texts)
    idx.add(vecs.astype(np.float32))
    for i, text in enumerate(texts):
        entry = {"text": text}
        if metadatas and i < len(metadatas):
            entry.update(metadatas[i])
        _metadata.append(entry)
    _save_index()


def build_index(texts: List[str], metadatas: Optional[List[Dict]] = None):
    """Rebuild the index from scratch."""
    global _faiss_index, _metadata
    import faiss

    dim = _get_embedder().get_sentence_embedding_dimension()
    _faiss_index = faiss.IndexFlatIP(dim)
    _metadata = []
    if texts:
        add_documents(texts, metadatas)
    else:
        _save_index()


def retrieve(query_text: str, top_k: int = 5) -> List[Tuple[float, Dict]]:
    """
    Return the top-k most similar documents to the query.

    Returns:
        List of (similarity_score, metadata_dict) tuples, highest first.
    """
    idx = _get_index()
    if idx.ntotal == 0:
        return []
    vec = _embed([query_text]).astype(np.float32)
    scores, indices = idx.search(vec, min(top_k, idx.ntotal))
    results = []
    for score, i in zip(scores[0], indices[0]):
        if i < 0:
            continue
        results.append((float(score), _metadata[i]))
    return results


def retrieve_and_format(query_text: str, top_k: int = 3) -> str:
    """
    Retrieve similar documents and format them as context for an LLM prompt.
    """
    hits = retrieve(query_text, top_k=top_k)
    if not hits:
        return "(No similar historical events found in the knowledge base.)"
    lines = ["Similar historical events:"]
    for rank, (score, meta) in enumerate(hits, 1):
        lines.append(f"  {rank}. [score={score:.3f}] {meta.get('text', '')}")
    return "\n".join(lines)
