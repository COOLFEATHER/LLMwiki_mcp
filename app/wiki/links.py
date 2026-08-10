"""双向链接图谱：维护 links.json（page → 出链/入链）。

比纯文本 [[xxx]] 扫描更可维护：重命名/删除做影响分析、查孤儿、图遍历。
每次 Ingest 更新页面后调用 save_graph() 刷新。
"""
from __future__ import annotations

import json

from app.config import settings
from app.wiki.storage import list_pages, read_page


def build_graph() -> dict:
    """扫描全部 wiki 页，构建 {page: {outlinks: [], inlinks: []}}。"""
    graph: dict[str, dict[str, list[str]]] = {}
    for name in list_pages():
        graph.setdefault(name, {"outlinks": [], "inlinks": []})
    for name in list(graph):
        try:
            outs = read_page(name).outlinks()
        except Exception:
            outs = []
        graph[name]["outlinks"] = outs
        for target in outs:
            graph.setdefault(target, {"outlinks": [], "inlinks": []})["inlinks"].append(name)
    return graph


def save_graph(graph: dict | None = None) -> dict:
    """构建（或用传入的）图谱并持久化到 links.json，返回图谱。"""
    graph = graph or build_graph()
    settings.links_file.parent.mkdir(parents=True, exist_ok=True)
    settings.links_file.write_text(
        json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return graph


def load_graph() -> dict:
    if not settings.links_file.exists():
        return {}
    return json.loads(settings.links_file.read_text(encoding="utf-8"))


def orphans() -> list[str]:
    """无入链的孤儿页面（含尚未建页的悬空链接目标）。"""
    g = load_graph() or build_graph()
    return sorted(name for name, links in g.items() if not links.get("inlinks"))


def backlinks(page: str) -> list[str]:
    """某页的反向入链。"""
    g = load_graph() or build_graph()
    return g.get(page, {}).get("inlinks", [])
