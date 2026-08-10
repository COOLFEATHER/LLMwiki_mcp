"""轻量 embedding —— 三种模式，由 EMBED_PROVIDER 环境变量控制。

模式:
  api   → OpenAI 兼容 API（需配置 EMBED_API_KEY + EMBED_API_URL）
  local → 本地 TF-IDF 哈希向量（纯 numpy，无外部依赖）
  off   → 关闭向量检索，仅用 BM25

用法:
  from app.embed import get_embedder
  embedder = get_embedder()    # 按 config 自动选择
  vecs = embedder.embed(["text1", "text2"])
"""
from __future__ import annotations

import math
import os
from collections import Counter
from typing import Protocol

from app.config import settings


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class APIEmbedder:
    """通过 OpenAI 兼容 API 调用 embedding 模型。

    需要设置:
      EMBED_API_KEY   (或 OPENAI_API_KEY)
      EMBED_API_URL   (或 OPENAI_BASE_URL)
      EMBED_MODEL     (默认 text-embedding-3-small)
    """

    def __init__(self):
        self._api_key = settings.embed_api_key or os.getenv("OPENAI_API_KEY", "")
        self._base_url = settings.embed_api_url or os.getenv("OPENAI_BASE_URL", "")
        self._model = settings.embed_model
        self._client = None

    def _ensure(self):
        if self._client is None:
            if not self._api_key:
                raise RuntimeError(
                    "EMBED_PROVIDER=api 但未设置 EMBED_API_KEY 或 OPENAI_API_KEY"
                )
            from openai import OpenAI
            kwargs = {"api_key": self._api_key}
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = OpenAI(**kwargs)
        return self._client

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        client = self._ensure()
        resp = client.embeddings.create(model=self._model, input=texts)
        sorted_data = sorted(resp.data, key=lambda d: d.index)
        return [d.embedding for d in sorted_data]


class TfidfEmbedder:
    """本地 TF-IDF 哈希向量（纯 numpy，无外部依赖）。

    用字符级 n-gram + tf-idf 权重 + 特征哈希生成固定维度向量。
    效果不如语义 embedding，但能区分不同主题的文本。
    """

    def __init__(self, dim: int | None = None):
        self.dim = dim or settings.embed_dim

    def _features(self, text: str) -> Counter:
        feats: Counter = Counter()
        text_lower = text.lower()
        for ch in text_lower:
            if ch.strip():
                feats[ch] += 1
        for i in range(len(text_lower) - 1):
            bg = text_lower[i : i + 2]
            if bg.strip():
                feats[bg] += 1
        return feats

    def _hash_vec(self, feats: Counter) -> list[float]:
        vec = [0.0] * self.dim
        for token, freq in feats.items():
            h = hash(token) % self.dim
            vec[h] += math.log(1 + freq)
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._hash_vec(self._features(t)) for t in texts]


class NoopEmbedder:
    """向量检索关闭时使用。embed() 返回空列表。"""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return []


# ── 全局单例缓存 ────────────────────────────────────────
_api_embedder: APIEmbedder | None = None
_tfidf_embedder: TfidfEmbedder | None = None
_noop_embedder: NoopEmbedder | None = None


def get_embedder() -> Embedder:
    """按 settings.embed_provider 返回对应的 embedder。"""
    global _api_embedder, _tfidf_embedder, _noop_embedder

    provider = settings.embed_provider

    if provider == "api":
        if _api_embedder is None:
            _api_embedder = APIEmbedder()
        return _api_embedder

    if provider == "local":
        if _tfidf_embedder is None:
            _tfidf_embedder = TfidfEmbedder()
        return _tfidf_embedder

    # "off" 或任何其他值 → Noop
    if _noop_embedder is None:
        _noop_embedder = NoopEmbedder()
    return _noop_embedder
