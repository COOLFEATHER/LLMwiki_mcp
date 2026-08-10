"""自实现 BM25 关键词召回（纯 Python，无外部依赖）。

替代 rank-bm25 + jieba 两重依赖。
内置一个极简中文分词（按字符 + 常见双字组合），也支持英文空格分词。
如果环境有 jieba，自动使用 jieba 以获得更好效果。
"""
from __future__ import annotations

import math
from collections import Counter


def _tokenize(text: str) -> list[str]:
    """分词：优先用 jieba，fallback 到简单 char-gram 分词。"""
    try:
        import jieba
        return [t for t in jieba.cut(text) if t.strip()]
    except ImportError:
        pass
    # 简易分词：英文按空格，中文按字 + 双字组合
    tokens: list[str] = []
    for word in text.split():
        if word.encode("utf-8").isalpha():
            tokens.append(word.lower())
        else:
            # 中文：单字 + 双字滑动
            for ch in word:
                if ch.strip():
                    tokens.append(ch)
            for i in range(len(word) - 1):
                bigram = word[i : i + 2]
                if bigram.strip():
                    tokens.append(bigram)
    return tokens


class BM25Okapi:
    """BM25-Okapi 实现。"""

    def __init__(self, corpus: list[str]):
        self._tokenized: list[list[str]] = [_tokenize(doc) for doc in corpus]
        self._avgdl = sum(len(t) for t in self._tokenized) / max(len(self._tokenized), 1)
        # IDF 计算
        self._idf: dict[str, float] = {}
        doc_freq: Counter[str] = Counter()
        for tokens in self._tokenized:
            for t in set(tokens):
                doc_freq[t] += 1
        n = len(self._tokenized)
        for t, df in doc_freq.items():
            self._idf[t] = math.log(1 + (n - df + 0.5) / (df + 0.5))

    def _score(self, query_tokens: list[str], doc_tokens: list[str]) -> float:
        """单个文档的 BM25 分数。"""
        k1, b = 1.5, 0.75
        dl = len(doc_tokens)
        tf_counter = Counter(doc_tokens)
        score = 0.0
        for qt in set(query_tokens):
            if qt not in self._idf:
                continue
            tf = tf_counter.get(qt, 0)
            score += self._idf[qt] * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / self._avgdl))
        return score

    def get_scores(self, query: str) -> list[float]:
        """返回所有文档的 BM25 分数列表。"""
        qtokens = _tokenize(query)
        return [self._score(qtokens, doc_tokens) for doc_tokens in self._tokenized]


def tokenize(text: str) -> list[str]:
    """外部可用的分词函数。"""
    return _tokenize(text)
