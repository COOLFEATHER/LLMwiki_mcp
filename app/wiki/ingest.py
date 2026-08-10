"""Ingest 编译循环：raw 素材 → LLM → 更新多个 Wiki 页 + 建链 + 标矛盾。

LLM Wiki 的核心引擎。不依赖 app.llm.client，而是接收一个 chat 函数（开闭原则）。
一篇素材可触发 5-15 处页面修改。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.config import settings
from app.wiki.links import save_graph
from app.wiki.metadata import now_ts
from app.wiki.page import WikiPage
from app.wiki.storage import list_pages, page_exists, read_page, write_page


@dataclass
class IngestResult:
    raw_path: str
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"Ingest {self.raw_path}: 新建 {self.created}，"
            f"更新 {self.updated}，错误 {self.errors}"
        )


def _build_prompt(raw_text: str, raw_name: str, schema_text: str, existing: list[str]) -> list[dict]:
    sys = (
        "你是 LLM Wiki 的编译引擎。读取原始素材，按 SCHEMA 提取概念/实体，"
        "为每个产出或更新一个 Wiki 页（body 含 [[双向链接]] 互联）。"
        "检测与既有结论矛盾时生成 contradiction 页。\n\n"
        f"--- SCHEMA ---\n{schema_text}\n\n"
        f"--- 已有 Wiki 页 ---\n{', '.join(existing) or '(无)'}\n"
    )
    user = (
        f"素材文件：{raw_name}\n\n--- 素材内容 ---\n{raw_text}\n\n"
        "只输出 JSON，格式：\n"
        '{"pages":[{"action":"create|update","title":"","type":"concept|entity|summary|index|contradiction",'
        '"body":"markdown 含 [[链接]]","tags":[],"sources":["raw/xxx.md"],"confidence":0.0~1.0}]}'
    )
    return [
        {"role": "system", "content": sys},
        {"role": "user", "content": user},
    ]


def _extract_json(text: str) -> dict:
    """从 LLM 输出提取首个 JSON 对象。"""
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1]
        if s.endswith("```"):
            s = s.rsplit("```", 1)[0]
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("LLM 输出未找到 JSON 对象")
    return json.loads(s[start : end + 1])


def _apply_op(op: dict, raw_name: str) -> tuple[str, str]:
    """应用单个页面操作，返回 (title, 'created'|'updated')。"""
    title = op["title"]
    existed = page_exists(title)
    sources = list(dict.fromkeys(op.get("sources", []) + [f"raw/{raw_name}"]))
    if existed:
        old = read_page(title)
        page = WikiPage(
            title=title,
            page_type=op.get("type") or old.page_type,
            body=op.get("body") or old.body,
            tags=list(dict.fromkeys(old.tags + op.get("tags", []))),
            sources=list(dict.fromkeys(old.sources + sources)),
            created=old.created,
            updated=now_ts(),
            confidence=float(op.get("confidence", old.confidence)),
            category=old.category,
            extra=old.extra,
        )
        status = "updated"
    else:
        ts = now_ts()
        page = WikiPage(
            title=title,
            page_type=op.get("type", "concept"),
            body=op.get("body", ""),
            tags=list(op.get("tags", [])),
            sources=sources,
            created=ts,
            updated=ts,
            confidence=float(op.get("confidence", 1.0)),
        )
        status = "created"
    write_page(page)
    return title, status


def ingest(raw_path: str | Path, chat_fn: callable) -> IngestResult:
    """编译一份 raw 素材为 Wiki 页更新。

    参数:
        raw_path: raw 文件路径
        chat_fn: 调用 LLM 的函数，接收 messages list[dict]，返回 str
    """
    p = Path(raw_path)
    raw_text = p.read_text(encoding="utf-8")
    raw_name = p.name

    schema_text = (
        settings.schema_file.read_text(encoding="utf-8")
        if settings.schema_file.exists()
        else ""
    )
    existing = list_pages()

    messages = _build_prompt(raw_text, raw_name, schema_text, existing)
    reply = chat_fn(messages)
    data = _extract_json(reply)

    result = IngestResult(raw_path=str(p))
    for raw_op in data.get("pages", []):
        try:
            title, status = _apply_op(raw_op, raw_name)
            (result.created if status == "created" else result.updated).append(title)
        except Exception as e:
            result.errors.append(f"{raw_op.get('title', '?')}: {e}")

    save_graph()
    return result
