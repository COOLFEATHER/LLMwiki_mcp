"""WikiPage：frontmatter + body 的解析、序列化，[[双向链接]] 提取。

一个 Wiki 页 = YAML frontmatter + Markdown body。
[[页面名]] 语法提取出链；links.py 据此维护 links.json 反向入链。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import yaml

from app.wiki.schema import validate_frontmatter

_LINK_RE = re.compile(r"\[\[([^\]]+?)\]\]")
_FM_RE = re.compile(r"^---\s*\n(.*?\n)---\s*\n?(.*)$", re.S)


def page_key(name: str) -> str:
    """[[显示名]] → 规范页面键：去首尾空格、内部空格转下划线。与文件 stem 一致。"""
    return name.strip().replace(" ", "_")


@dataclass
class WikiPage:
    title: str
    page_type: str
    body: str
    tags: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    created: str = ""
    updated: str = ""
    confidence: float = 1.0
    category: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def frontmatter(self) -> dict:
        fm: dict = {
            "title": self.title,
            "type": self.page_type,
            "tags": self.tags,
            "sources": self.sources,
            "created": self.created,
            "updated": self.updated,
            "confidence": self.confidence,
        }
        if self.category:
            fm["category"] = self.category
        fm.update(self.extra)
        return fm

    def outlinks(self) -> list[str]:
        """提取 body 中所有 [[页面名]]，规范化为页面键（空格转下划线），去重保序。"""
        seen: set[str] = set()
        out: list[str] = []
        for name in _LINK_RE.findall(self.body):
            key = page_key(name)
            if key not in seen:
                seen.add(key)
                out.append(key)
        return out

    def validation_errors(self) -> list[str]:
        return validate_frontmatter(self.frontmatter)


def parse_page(text: str) -> WikiPage:
    """从 md 文本解析出 WikiPage。无 frontmatter 或非法则抛 ValueError。"""
    m = _FM_RE.match(text)
    if not m:
        raise ValueError("缺少 YAML frontmatter（需以 --- 包裹）")
    fm = yaml.safe_load(m.group(1)) or {}
    if not isinstance(fm, dict):
        raise ValueError("frontmatter 必须是字典")
    body = m.group(2)
    errors = validate_frontmatter(fm)
    if errors:
        raise ValueError("frontmatter 非法: " + "; ".join(errors))
    known = {"title", "type", "tags", "sources", "created", "updated", "confidence", "category"}
    return WikiPage(
        title=fm["title"],
        page_type=fm["type"],
        body=body,
        tags=list(fm.get("tags") or []),
        sources=list(fm.get("sources") or []),
        created=fm.get("created", ""),
        updated=fm.get("updated", ""),
        confidence=float(fm.get("confidence", 1.0)),
        category=fm.get("category", ""),
        extra={k: v for k, v in fm.items() if k not in known},
    )


def serialize_page(page: WikiPage) -> str:
    """序列化为 md 文本（frontmatter + body）。"""
    fm_yaml = yaml.safe_dump(page.frontmatter, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{fm_yaml}\n---\n\n{page.body.rstrip()}\n"
