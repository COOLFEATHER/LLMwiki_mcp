"""Markdown 结构化切片：按标题层级切分 Wiki 页正文。

直接从 WikiPage 对象切片，元数据由调用方传入。
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.M)


@dataclass
class Chunk:
    """一个检索单元。"""
    page: str
    heading: str
    text: str
    metadata: dict = field(default_factory=dict)


def chunk_page(page) -> list[Chunk]:
    """按标题切分 WikiPage.body，返回 Chunk 列表。

    参数 page 是 WikiPage 实例（有 .title, .body, .page_type, .tags, .sources, .confidence）。
    """
    base_meta = {
        "type": page.page_type,
        "tags": page.tags,
        "sources": page.sources,
        "confidence": page.confidence,
    }
    body = page.body
    matches = list(_HEADING_RE.finditer(body))
    if not matches:
        stripped = body.strip()
        return [Chunk(page=page.title, heading="", text=stripped, metadata=base_meta)] if stripped else []

    chunks: list[Chunk] = []
    pre = body[: matches[0].start()].strip()
    if pre:
        chunks.append(Chunk(page=page.title, heading="", text=pre, metadata=base_meta))

    stack: list[tuple[int, str]] = []
    for i, m in enumerate(matches):
        level = len(m.group(1))
        title = m.group(2).strip()
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        heading_path = " > ".join(t for _, t in stack)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        text = body[start:end].strip()
        if text:
            chunks.append(Chunk(page=page.title, heading=heading_path, text=text, metadata=base_meta))
    return chunks


def chunk_markdown(page_name: str, md_text: str) -> list[Chunk]:
    """解析 md 文本（含 frontmatter）后切片。"""
    from app.wiki.page import parse_page
    return chunk_page(parse_page(md_text))


def chunk_id(c: Chunk) -> str:
    """内容哈希作为 chunk 唯一 id。"""
    return hashlib.sha1(f"{c.page}::{c.heading}::{c.text}".encode()).hexdigest()[:16]
