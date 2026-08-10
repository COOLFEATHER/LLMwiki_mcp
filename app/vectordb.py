"""扁平 JSON 向量索引（替代 Chroma）。

存储结构：
  {
    "chunks": [
      {"id": "sha1", "page": "...", "heading": "...", "text": "...",
       "vector": [0.1, 0.2, ...], "metadata": {...}}
    ]
  }

加载到内存后用暴力余弦相似度检索（千级 chunk < 10ms，万级 < 100ms）。
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from app.config import settings
from app.embed import get_embedder


# 内存缓存
_index_data: dict | None = None
_dirty = False


def _index_path() -> Path:
    return settings.index_file


def _ensure_loaded() -> dict:
    global _index_data
    global _dirty
    if _index_data is None:
        p = _index_path()
        if p.exists():
            _index_data = json.loads(p.read_text(encoding="utf-8"))
        else:
            _index_data = {"chunks": []}
        _dirty = False
    return _index_data


def _save() -> None:
    global _dirty
    if _index_data is not None:
        p = _index_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(_index_data, ensure_ascii=False), encoding="utf-8")
    _dirty = False


def chunk_id(page: str, heading: str, text: str) -> str:
    return hashlib.sha1(f"{page}::{heading}::{text}".encode()).hexdigest()[:16]


def upsert(chunks: list[dict], embeddings: list[list[float]]) -> None:
    """更新/插入 chunks。

    chunks: [{"page": str, "heading": str, "text": str, "metadata": dict}, ...]
    embeddings: 与 chunks 等长的向量列表
    """
    global _dirty
    data = _ensure_loaded()
    existing = {c["id"]: i for i, c in enumerate(data["chunks"])}

    batch: list[dict] = []
    for c, vec in zip(chunks, embeddings):
        cid = chunk_id(c["page"], c["heading"], c["text"])
        batch.append({
            "id": cid,
            "page": c["page"],
            "heading": c["heading"],
            "text": c["text"],
            "vector": vec,
            "metadata": c.get("metadata", {}),
        })

    # 先删再追加（批量 upsert）
    new_ids = {b["id"] for b in batch}
    data["chunks"] = [c for c in data["chunks"] if c["id"] not in new_ids]
    data["chunks"].extend(batch)
    _dirty = True


def _cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def query_vector(query_embedding: list[float], top_k: int = 10) -> list[tuple[dict, float]]:
    """语义检索，返回 [(chunk_dict, score), ...]，按 score 降序。"""
    data = _ensure_loaded()
    scored: list[tuple[dict, float]] = []
    for c in data["chunks"]:
        sim = _cosine_sim(query_embedding, c["vector"])
        scored.append((c, sim))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


def chunks_of_pages(pages: list[str]) -> list[dict]:
    """取指定页面集合的所有 chunk。"""
    data = _ensure_loaded()
    page_set = set(pages)
    return [c for c in data["chunks"] if c["page"] in page_set]


def delete_by_page(page: str) -> int:
    """删除某个页面的所有 chunk，返回删除数。"""
    global _dirty
    data = _ensure_loaded()
    before = len(data["chunks"])
    data["chunks"] = [c for c in data["chunks"] if c["page"] != page]
    n = before - len(data["chunks"])
    if n:
        _dirty = True
    return n


def rebuild(wiki_dir: Path, embedder=None) -> int:
    """全量重建索引。

    如果 embedding 启用，生成向量并存储。
    如果 EMBED_PROVIDER=off，只存储文本（向量为空列表），查询时纯 BM25。
    """
    from app.rag.chunker import chunk_page
    from app.wiki.storage import list_pages, read_page

    embedder = embedder or get_embedder()
    all_chunks: list[dict] = []
    all_texts: list[str] = []
    for name in list_pages():
        try:
            page = read_page(name)
            for c in chunk_page(page):
                all_chunks.append({
                    "page": c.page,
                    "heading": c.heading,
                    "text": c.text,
                    "metadata": dict(c.metadata),
                })
                all_texts.append(c.text)
        except Exception as e:
            print(f"[rebuild] skip {name}: {e}")

    if not all_chunks:
        return 0

    if settings.embed_enabled:
        embeddings = embedder.embed(all_texts)
    else:
        # embedding 关闭，存空向量占位
        embeddings = [[] for _ in all_texts]

    upsert(all_chunks, embeddings)
    _save()
    return len(all_chunks)


def ensure_saved() -> None:
    """持久化到磁盘（在 MCP 工具返回前调用）。"""
    if _dirty:
        _save()
