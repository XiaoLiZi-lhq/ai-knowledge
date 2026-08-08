"""
AI Knowledge Hub - 轻量级中文嵌入引擎
零外部依赖（仅 jieba），基于字符级 n-gram + 词级 TF-IDF 混合方案
向量维度: 384，L2 归一化，兼容 ChromaDB
"""

import hashlib
import math
import re
from collections import Counter
from typing import List

import jieba
import jieba.analyse

# 向量维度
EMBED_DIM = 384


class LocalEmbedding:
    """本地嵌入引擎 - 不依赖任何外部模型下载"""

    def __init__(self, dim: int = EMBED_DIM):
        self.dim = dim
        # 预热 jieba 词典
        jieba.initialize()

    def _char_ngrams(self, text: str, n: int = 2) -> List[str]:
        """提取字符级 n-gram（bigram）"""
        text = re.sub(r"\s+", "", text)
        return [text[i:i+n] for i in range(len(text) - n + 1)] if len(text) >= n else [text]

    def _hash_to_vec(self, tokens: List[str], dim: int, salt: str = "") -> List[float]:
        """将 token 列表通过哈希映射到固定维度向量（hashing trick）"""
        vec = [0.0] * dim
        for token in tokens:
            h = hashlib.md5(f"{salt}{token}".encode()).hexdigest()
            idx = int(h[:8], 16) % dim
            sign = 1.0 if int(h[8:16], 16) % 2 == 0 else -1.0
            vec[idx] += sign
        return vec

    def _l2_normalize(self, vec: List[float]) -> List[float]:
        """L2 归一化"""
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0:
            return vec
        return [v / norm for v in vec]

    def embed_one(self, text: str) -> List[float]:
        """生成单条文本的嵌入向量"""
        if not text or not text.strip():
            return [0.0] * self.dim

        # 1. jieba 分词（带权重）
        words = list(jieba.cut(text))
        # 过滤停用词和短词
        words = [w.strip() for w in words if len(w.strip()) >= 2]

        # 2. 关键词提取
        keywords = jieba.analyse.extract_tags(text, topK=20, withWeight=True)

        # 3. 字符 bigram
        char_grams = self._char_ngrams(text, n=2)

        # 4. 混合向量：分3段，分别用不同盐值
        dim_third = self.dim // 3
        remaining = self.dim - dim_third * 3

        vec_words = self._hash_to_vec(words, dim_third, salt="word")
        vec_chars = self._hash_to_vec(char_grams, dim_third, salt="char")
        vec_kw = [0.0] * dim_third
        for kw, weight in keywords:
            h = hashlib.md5(f"kw{kw}".encode()).hexdigest()
            idx = int(h[:8], 16) % dim_third
            sign = 1.0 if int(h[8:16], 16) % 2 == 0 else -1.0
            vec_kw[idx] += sign * weight

        # 5. 剩余维度用三元组填充（如果 remaining > 0）
        if remaining > 0:
            char_3grams = self._char_ngrams(text, n=3)
            vec_tri = self._hash_to_vec(char_3grams, remaining, salt="tri")
        else:
            vec_tri = []

        # 拼接
        full_vec = vec_words + vec_chars + vec_kw + vec_tri

        # 6. L2 归一化
        return self._l2_normalize(full_vec)

    def embed(self, texts: List[str]) -> List[List[float]]:
        """批量生成嵌入向量"""
        return [self.embed_one(t) for t in texts]


# 全局单例
local_embedder = LocalEmbedding()
