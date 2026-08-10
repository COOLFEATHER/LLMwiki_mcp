"""全局配置：路径、模型、检索参数（轻量化版）。

砍掉了 chroma / langgraph / memory / watchdog 相关配置。
embedding 通过 API 调用（OpenAI 兼容），无需本地模型。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    # —— 运行时数据根 ——
    data_dir: Path = Path("data")
    raw_dir: Path = Path("data/raw")
    wiki_dir: Path = Path("data/wiki")
    links_file: Path = Path("data/links.json")
    schema_file: Path = Path("SCHEMA.md")
    index_file: Path = Path("data/index.json")   # 扁平向量索引

    # —— LLM ——
    chat_model: str = os.getenv("CHAT_MODEL", "deepseek-chat")

    # —— Embedding（三种模式：api / local / off）——
    #   api:    OpenAI 兼容 API（需 PROVIDER_API_KEY + EMBED_API_URL）
    #   local:  本地 TF-IDF 向量（纯 numpy，无外部依赖）
    #   off:    关闭向量检索，仅用 BM25（最轻量）
    embed_provider: str = os.getenv("EMBED_PROVIDER", "local")
    embed_model: str = os.getenv("EMBED_MODEL", "text-embedding-3-small")
    embed_dim: int = int(os.getenv("EMBED_DIM", "256"))
    embed_api_key: str = os.getenv("EMBED_API_KEY", "")
    embed_api_url: str = os.getenv("EMBED_API_URL", "")

    @property
    def embed_enabled(self) -> bool:
        return self.embed_provider != "off"

    # —— 检索参数 ——
    top_k_vector: int = 10
    top_k_bm25: int = 10
    rrf_k: int = 60
    final_k: int = 5
    link_expansion_hops: int = 1


settings = Settings()
