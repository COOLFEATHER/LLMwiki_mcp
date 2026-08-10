"""自动元数据：时间戳、frontmatter 生成与刷新。"""
from __future__ import annotations

from datetime import datetime, timezone

from app.wiki.page import WikiPage


def now_ts() -> str:
    """本地时区 ISO8601 时间戳（秒精度）。"""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def build_frontmatter(
    title: str,
    page_type: str,
    tags: list[str] | None = None,
    sources: list[str] | None = None,
    confidence: float = 1.0,
    category: str = "",
) -> dict:
    """生成最小合法 frontmatter。"""
    ts = now_ts()
    return {
        "title": title,
        "type": page_type,
        "tags": list(tags or []),
        "sources": list(sources or []),
        "created": ts,
        "updated": ts,
        "confidence": confidence,
        **({"category": category} if category else {}),
    }


def touch_updated(page: WikiPage) -> WikiPage:
    """刷新 updated 时间戳，返回同一对象。"""
    page.updated = now_ts()
    return page
