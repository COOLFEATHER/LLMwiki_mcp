"""Wiki 页面文件读写：frontmatter + body。

Wiki 是 LLM 编译产物（派生），Raw 才是不可变真源。
文件名 = page 名（空格转下划线），存于 data/wiki/。
"""
from __future__ import annotations

from pathlib import Path

from app.config import settings
from app.wiki.page import WikiPage, page_key, parse_page, serialize_page


def page_path(page: str) -> Path:
    """页面名 → 文件路径（规范化为页面键）。"""
    return settings.wiki_dir / f"{page_key(page)}.md"


def read_page(page: str) -> WikiPage:
    """读取并解析页面。文件缺失抛 FileNotFoundError。"""
    text = page_path(page).read_text(encoding="utf-8")
    return parse_page(text)


def write_page(page: WikiPage) -> Path:
    """写入页面（frontmatter + body），返回路径。非法页面拒绝写入。"""
    errors = page.validation_errors()
    if errors:
        raise ValueError("拒绝写入非法页面: " + "; ".join(errors))
    p = page_path(page.title)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(serialize_page(page), encoding="utf-8")
    return p


def list_pages() -> list[str]:
    """列出 wiki_dir 下所有页面名（文件名去扩展名）。"""
    if not settings.wiki_dir.exists():
        return []
    return sorted(p.stem for p in settings.wiki_dir.glob("*.md"))


def page_exists(page: str) -> bool:
    return page_path(page).exists()
