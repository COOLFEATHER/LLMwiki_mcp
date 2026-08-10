"""LLM Wiki MCP Server（轻量化版）。

依赖: fastmcp + openai + pyyaml + python-dotenv
无: chromadb / sentence-transformers / langgraph / watchdog / rank-bm25

环境变量:
  OPENAI_API_KEY        LLM chat API key（ingest 编译需要）
  OPENAI_BASE_URL       LLM API 地址（如 https://api.deepseek.com）
  CHAT_MODEL            对话模型名（默认 deepseek-chat）
  EMBED_PROVIDER        embedding 模式: api / local / off（默认 local）
  EMBED_API_KEY         embedding API key（EMBED_PROVIDER=api 时需要）
  EMBED_API_URL         embedding API 地址（可选，默认同 OPENAI_BASE_URL）
  EMBED_MODEL           embedding 模型名（默认 text-embedding-3-small）

启动: python server.py  或  pip install -e . && llm-wiki-server
"""
from __future__ import annotations

import os
from pathlib import Path

# 尽早加载 .env，确保 import 其他模块前环境变量就绪
from dotenv import load_dotenv
load_dotenv()

from fastmcp import FastMCP

from app.config import settings

mcp = FastMCP("llm-wiki")


# ── LLM chat 封装 ──────────────────────────────────────────
def _chat(messages: list[dict]) -> str:
    """调用 LLM chat completion。"""
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("未设置 OPENAI_API_KEY，无法调用 LLM")
    base_url = os.getenv("OPENAI_BASE_URL", "")
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(**kwargs)
    resp = client.chat.completions.create(
        model=settings.chat_model,
        messages=messages,
        temperature=0.2,
    )
    return resp.choices[0].message.content or ""


# ── RAG 检索（BM25 + 向量 + RRF + 链接扩展）───────────────
def _ensure_index():
    """索引不存在时自动重建。"""
    if not settings.index_file.exists():
        from app.vectordb import rebuild
        rebuild(settings.wiki_dir)


def _retrieve(query: str) -> list[dict]:
    """混合检索，返回按相关性排序的 chunk dict 列表。

    取决于 EMBED_PROVIDER 配置：
      api/local → 向量 + BM25 + RRF + 链接扩展
      off       → BM25 + 链接扩展（最轻量）
    """
    _ensure_index()
    from app.bm25 import BM25Okapi, tokenize
    from app.embed import get_embedder
    from app.vectordb import query_vector, chunks_of_pages
    from app.wiki.links import load_graph
    from app.vectordb import _ensure_loaded

    data = _ensure_loaded()
    all_texts = [c["text"] for c in data.get("chunks", [])]

    # 1. BM25 检索（始终可用，不依赖任何外部服务）
    bm25 = BM25Okapi(all_texts) if all_texts else None
    bm_scores = bm25.get_scores(query) if bm25 else []
    bm_ranked = sorted(
        [(data["chunks"][i], bm_scores[i]) for i in range(len(bm_scores)) if bm_scores[i] > 0],
        key=lambda x: x[1], reverse=True
    )[:settings.top_k_bm25]

    # 2. 向量检索（根据配置决定是否启用）
    vec_hits: list[tuple[dict, float]] = []
    if settings.embed_enabled:
        embedder = get_embedder()
        qvec = embedder.embed([query])[0]
        if qvec:  # 有向量才查
            vec_hits = query_vector(qvec, top_k=settings.top_k_vector)

    # 3. RRF 融合
    seen_keys: set[str] = set()
    results: list[dict] = []
    for hits in (vec_hits, bm_ranked):
        for rank, (chunk, _) in enumerate(hits):
            key = f"{chunk['page']}::{chunk['heading']}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            results.append(chunk)
    results = results[:settings.final_k]

    # 4. 链接扩展：出链/入链 + 邻居页 chunk
    if results and settings.link_expansion_hops > 0:
        seed_pages = list(dict.fromkeys(c["page"] for c in results))
        g = load_graph()
        expanded: set[str] = set(seed_pages)
        frontier = list(seed_pages)
        for _ in range(settings.link_expansion_hops):
            nxt: list[str] = []
            for p in frontier:
                node = g.get(p, {})
                for t in node.get("outlinks", []) + node.get("inlinks", []):
                    if t not in expanded:
                        expanded.add(t)
                        nxt.append(t)
            if not nxt:
                break
            frontier = nxt
        extra = chunks_of_pages(list(expanded))
        extra_pages = {c["page"] for c in results}
        for c in extra:
            if c["page"] not in extra_pages:
                results.append(c)
                extra_pages.add(c["page"])

    return results


# ── MCP 工具 ───────────────────────────────────────────────
@mcp.tool()
def ingest(raw_path: str) -> str:
    """编译一份原始素材为 Wiki 页（提取概念/建链/标矛盾）。

    Args:
        raw_path: raw 素材文件路径，如 "data/raw/sample_notes.md"
    """
    from app.wiki.ingest import ingest as _ingest
    from app.vectordb import rebuild

    result = _ingest(raw_path, chat_fn=_chat)
    # 重建索引（在实际的 ingest 中，可以只增量索引改动页）
    rebuild(settings.wiki_dir)
    return str(result)


@mcp.tool()
def query(question: str) -> str:
    """混合检索 + 链接扩展，返回相关 Wiki 片段。

    Args:
        question: 用户的问题
    """
    chunks = _retrieve(question)
    if not chunks:
        return "（无检索结果）"
    return "\n---\n".join(
        f"[{c['page']}] {c['text'][:300]}" for c in chunks
    )


@mcp.tool()
def write_wiki(title: str, body: str, page_type: str = "concept", tags: str = "") -> str:
    """新建一个 Wiki 页（自动生成 frontmatter）。

    Args:
        title: 页面标题
        body: Markdown 正文
        page_type: 页面类型（concept/entity/summary/index/contradiction）
        tags: 逗号分隔的标签
    """
    from app.wiki.metadata import build_frontmatter
    from app.wiki.page import WikiPage
    from app.wiki.storage import write_page as _write
    from app.wiki.links import save_graph
    from app.vectordb import rebuild

    fm = build_frontmatter(title, page_type, tags=[t.strip() for t in tags.split(",") if t.strip()])
    page = WikiPage(
        title=fm["title"], page_type=fm["type"], tags=fm["tags"],
        sources=[], created=fm["created"], updated=fm["updated"],
        confidence=1.0, body=body,
    )
    path = _write(page)
    save_graph()
    rebuild(settings.wiki_dir)
    return f"已写入 {path.name}"


@mcp.tool()
def read_wiki(page: str) -> str:
    """读取一个 Wiki 页全文（含 frontmatter）。

    Args:
        page: 页面标题（空格自动转下划线）
    """
    from app.wiki.page import serialize_page
    from app.wiki.storage import read_page as _read

    return serialize_page(_read(page))


@mcp.tool()
def rebuild_index() -> str:
    """全量重建向量 + BM25 索引（从现有 Wiki 页）。"""
    from app.vectordb import rebuild

    n = rebuild(settings.wiki_dir)
    return f"索引重建完成，共 {n} 个 chunk"


def _print_status():
    """打印启动状态信息。"""
    embed_mode = settings.embed_provider
    embed_desc = {
        "api": f"API ({settings.embed_model})",
        "local": "本地 TF-IDF",
        "off": "关闭（仅 BM25）",
    }.get(embed_mode, embed_mode)

    retrieval = "向量 + BM25 + RRF" if settings.embed_enabled else "BM25 + 链接扩展"
    if settings.embed_enabled:
        retrieval += " + 链接扩展"

    print(f"  🧠  LLM Wiki  MCP Server")
    print(f"  📦  检索:    {retrieval}")
    print(f"  🎯  Embed:   {embed_desc}")
    print(f"  📚  Wiki 页: {len(list(Path(settings.wiki_dir).glob('*.md')))} 页")
    print(f"  🔧  设置     EMBED_PROVIDER=api|local|off 切换模式")
    print()


def main() -> None:
    """启动 MCP server（stdio 传输）。"""
    # 确保目录存在
    settings.raw_dir.mkdir(parents=True, exist_ok=True)
    settings.wiki_dir.mkdir(parents=True, exist_ok=True)

    _print_status()
    mcp.run()


if __name__ == "__main__":
    main()
