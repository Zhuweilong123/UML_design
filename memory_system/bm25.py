"""
BM25 稀疏向量索引

标准 BM25 (Okapi BM25) 算法实现, 用于文本检索。

公式:
  score(D, Q) = Σ IDF(q_i) × (f(q_i, D) × (k1 + 1)) / (f(q_i, D) + k1 × (1 - b + b × |D| / avgdl))

其中:
  - IDF(q_i) = ln((N - n(q_i) + 0.5) / (n(q_i) + 0.5) + 1)
  - f(q_i, D) = 词项 q_i 在文档 D 中的词频
  - |D| = 文档 D 的长度 (token 数)
  - avgdl = 所有文档的平均长度
  - N = 文档总数
  - n(q_i) = 包含词项 q_i 的文档数
  - k1 = 1.5 (词频饱和度参数)
  - b = 0.75 (文档长度归一化参数)

数据结构:
  - 倒排索引: term → {doc_id: term_frequency}
  - 文档长度表: doc_id → token_count
  - 平均文档长度: 增量维护

使用示例:
    >>> bm25 = BM25Index()
    >>> bm25.add("doc1", "用户偏好组合优于继承")
    >>> bm25.add("doc2", "Django 项目使用 MVC 模式")
    >>> results = bm25.search("组合继承设计", top_k=2)
    >>> print(results)  # [("doc1", 1.234), ("doc2", 0.567)]
"""

import math
from typing import Dict, List, Optional, Tuple

from .tokenizer import tokenize_for_index, tokenize


class BM25Index:
    """
    BM25 索引 —— 稀疏向量检索核心.

    Parameters:
        k1: 词频饱和度参数 (默认 1.5, 范围 [1.2, 2.0])
        b:  文档长度归一化参数 (默认 0.75, 范围 [0.5, 1.0])

    支持增量添加/删除文档, 所有统计量实时更新.
    """

    __slots__ = (
        "k1", "b",
        "_inverted_index",  # term -> {doc_id: tf}
        "_doc_lengths",      # doc_id -> token_count
        "_doc_texts",        # doc_id -> original_text (for re-indexing)
        "_avgdl",            # 平均文档长度
    )

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        if k1 <= 0:
            raise ValueError(f"k1 must be positive, got {k1}")
        if not 0.0 <= b <= 1.0:
            raise ValueError(f"b must be in [0, 1], got {b}")

        self.k1 = k1
        self.b = b
        self._inverted_index: Dict[str, Dict[str, int]] = {}
        self._doc_lengths: Dict[str, int] = {}
        self._doc_texts: Dict[str, str] = {}
        self._avgdl: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, doc_id: str, text: str) -> None:
        """
        添加或更新文档.

        Args:
            doc_id: 文档唯一标识
            text:   文档文本内容 (用于分词和索引)

        Note: 若 doc_id 已存在, 会先删除旧索引再重建.
        """
        if not doc_id:
            raise ValueError("doc_id must not be empty")

        # 若已存在, 先移除
        if doc_id in self._doc_lengths:
            self.remove(doc_id)

        tokens = tokenize_for_index(text)
        if not tokens:
            return

        # 更新倒排索引
        tf_map: Dict[str, int] = {}
        for t in tokens:
            tf_map[t] = tf_map.get(t, 0) + 1

        for term, tf in tf_map.items():
            if term not in self._inverted_index:
                self._inverted_index[term] = {}
            self._inverted_index[term][doc_id] = tf

        # 更新文档长度
        self._doc_lengths[doc_id] = len(tokens)
        self._doc_texts[doc_id] = text

        # 更新平均文档长度
        self._update_avgdl()

    def remove(self, doc_id: str) -> bool:
        """
        移除文档.

        Returns:
            True 若文档存在并成功移除, False 若文档不存在.
        """
        if doc_id not in self._doc_lengths:
            return False

        # 从倒排索引中清除
        for term, postings in list(self._inverted_index.items()):
            if doc_id in postings:
                del postings[doc_id]
                # 清理空 posting list
                if not postings:
                    del self._inverted_index[term]

        del self._doc_lengths[doc_id]
        self._doc_texts.pop(doc_id, None)

        self._update_avgdl()
        return True

    def search(
        self,
        query: str,
        top_k: int = 5,
        score_threshold: float = 0.0,
    ) -> List[Tuple[str, float]]:
        """
        根据查询检索 top-k 文档.

        Args:
            query:           查询文本
            top_k:           返回的最大文档数
            score_threshold: 最低得分阈值 (低于此值的结果被过滤)

        Returns:
            [(doc_id, bm25_score), ...] 按得分降序排列
        """
        if not self._doc_lengths:
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        N = self.doc_count

        # 计算每个文档的 BM25 得分
        scores: Dict[str, float] = {}

        for qt in query_tokens:
            postings = self._inverted_index.get(qt, {})
            if not postings:
                continue

            n_qi = len(postings)  # 包含该词项的文档数
            idf = self._idf(N, n_qi)

            for doc_id, tf in postings.items():
                doc_len = self._doc_lengths[doc_id]
                # BM25 term score
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (
                    1 - self.b + self.b * doc_len / max(self._avgdl, 1.0)
                )
                term_score = idf * numerator / denominator
                scores[doc_id] = scores.get(doc_id, 0.0) + term_score

        # 排序 + 截断
        sorted_scores = sorted(
            scores.items(), key=lambda x: x[1], reverse=True
        )

        results: List[Tuple[str, float]] = []
        for doc_id, score in sorted_scores:
            if score < score_threshold:
                break
            results.append((doc_id, score))
            if len(results) >= top_k:
                break

        return results

    def clear(self) -> None:
        """清空索引中所有文档."""
        self._inverted_index.clear()
        self._doc_lengths.clear()
        self._doc_texts.clear()
        self._avgdl = 0.0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def doc_count(self) -> int:
        """已索引的文档数."""
        return len(self._doc_lengths)

    @property
    def vocab_size(self) -> int:
        """词汇表大小."""
        return len(self._inverted_index)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _idf(N: int, n_qi: int) -> float:
        """
        计算 IDF (Inverse Document Frequency).

        使用 Robertson-Sparck Jones 平滑公式:
          IDF = ln((N - n_qi + 0.5) / (n_qi + 0.5) + 1)
        """
        if n_qi <= 0:
            return 0.0
        return math.log((N - n_qi + 0.5) / (n_qi + 0.5) + 1.0)

    def _update_avgdl(self) -> None:
        """增量更新平均文档长度."""
        if not self._doc_lengths:
            self._avgdl = 0.0
        else:
            total = sum(self._doc_lengths.values())
            self._avgdl = total / len(self._doc_lengths)

    # ------------------------------------------------------------------
    # Debug / introspection
    # ------------------------------------------------------------------

    def get_doc_text(self, doc_id: str) -> Optional[str]:
        """获取文档原始文本 (仅用于调试)."""
        return self._doc_texts.get(doc_id)

    def __repr__(self) -> str:
        return (
            f"BM25Index(docs={self.doc_count}, vocab={self.vocab_size}, "
            f"avgdl={self._avgdl:.1f}, k1={self.k1}, b={self.b})"
        )

    def __contains__(self, doc_id: str) -> bool:
        return doc_id in self._doc_lengths
