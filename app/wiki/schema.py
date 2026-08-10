"""Wiki 数据模型：页面类型、frontmatter schema 与校验。

全系统地基——RAG 检索对象、Memory 沉淀归宿都是 Wiki 页。
页面类型与 frontmatter 规范在此集中定义，供 page/storage/links 复用。
"""
from __future__ import annotations

from enum import Enum


class PageType(str, Enum):
    """Wiki 页面类型。"""

    CONCEPT = "concept"                # 概念页：定义、要点、关联
    ENTITY = "entity"                  # 实体页：人/物/项目
    SUMMARY = "summary"                # 摘要页：对原始素材的综合摘要
    INDEX = "index"                    # 索引页：某主题下相关页导航
    CONTRADICTION = "contradiction"    # 矛盾标注页：冲突结论追踪


PAGE_TYPES = {t.value for t in PageType}

# frontmatter 字段规范
REQUIRED_FIELDS = ("title", "type", "created", "updated")
OPTIONAL_FIELDS = ("tags", "sources", "confidence", "category")
_KNOWN_FIELDS = set(REQUIRED_FIELDS) | set(OPTIONAL_FIELDS)


def validate_frontmatter(fm: dict) -> list[str]:
    """校验 frontmatter，返回错误列表（空表示合法）。"""
    errors: list[str] = []
    for f in REQUIRED_FIELDS:
        if f not in fm:
            errors.append(f"缺少必填字段: {f}")
    if "type" in fm and fm["type"] not in PAGE_TYPES:
        errors.append(f"非法 type: {fm['type']}，应为 {sorted(PAGE_TYPES)}")
    if "confidence" in fm:
        c = fm["confidence"]
        if not isinstance(c, (int, float)) or isinstance(c, bool) or not (0 <= c <= 1):
            errors.append(f"confidence 应为 0~1 数值: {c}")
    if "tags" in fm and not isinstance(fm["tags"], list):
        errors.append("tags 应为列表")
    if "sources" in fm and not isinstance(fm["sources"], list):
        errors.append("sources 应为列表")
    return errors
