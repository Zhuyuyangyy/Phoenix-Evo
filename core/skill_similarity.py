"""
skill_similarity: 技能相似度检测模块
V0.3 — Phoenix-Evo Curator

职责：
  - 计算技能之间的文本相似度（TF-IDF + Cosine）
  - 基于技能名称 + 内容识别近似重复
  - 提供分组建议（merge / keep-separator / independent）
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ----------------------------------------------------------------------
# Data structures
# ----------------------------------------------------------------------

@dataclass
class SimilarityResult:
    skill_a: str
    skill_b: str
    score: float          # 0.0 ~ 1.0
    name_sim: float       # 名称相似度
    content_sim: float    # 内容相似度
    recommendation: str  # "merge" | "review" | "independent"


@dataclass
class SkillVector:
    skill_id: str
    skill_name: str
    content: str
    tfidf: dict[str, float]


# ----------------------------------------------------------------------
# Text preprocessing
# ----------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Simple Chinese/English混合分词。"""
    text = text.lower()
    return re.findall(r"[\w\u4e00-\u9fff]{2,}", text)


def _compute_idf(documents: list[list[str]], vocab: set[str]) -> dict[str, float]:
    """计算每个词的 IDF 值。"""
    N = len(documents)
    doc_freq: Counter = Counter()
    for doc in documents:
        for term in set(doc):
            if term in vocab:
                doc_freq[term] += 1
    idf = {}
    for term in vocab:
        df = doc_freq.get(term, 0)
        idf[term] = math.log((N + 1) / (df + 1)) + 1
    return idf


def _tfidf_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    """将 token 列表转换为 TF-IDF 向量（稀疏字典）。"""
    tf: Counter = Counter(tokens)
    total = max(sum(tf.values()), 1)
    vec = {}
    for term, count in tf.items():
        if term in idf:
            vec[term] = (count / total) * idf[term]
    return vec


def _cosine_sim(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    """计算两个稀疏 TF-IDF 向量的余弦相似度。"""
    common_keys = set(vec_a) & set(vec_b)
    if not common_keys:
        return 0.0
    dot = sum(vec_a[k] * vec_b[k] for k in common_keys)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _name_similarity(name_a: str, name_b: str) -> float:
    """
    技能名称相似度。
    使用字符级 Jaccard（处理中文/英文混合）。
    """
    def _chars(s: str) -> set[str]:
        return set(s.lower().replace(" ", "").replace("_", "").replace("-", ""))
    ca, cb = _chars(name_a), _chars(name_b)
    if not ca or not cb:
        return 0.0
    inter = len(ca & cb)
    union = len(ca | cb)
    return inter / union if union > 0 else 0.0


# ----------------------------------------------------------------------
# SkillVectorizer: build TF-IDF from a list of skill entries
# ----------------------------------------------------------------------

class SkillVectorizer:
    """
    将技能列表向量化，支持相似度计算。

    用法:
        vectorizer = SkillVectorizer(skill_entries, root="/path/to/Phoenix-Evo")
        results = vectorizer.compute_pairwise()
    """

    def __init__(self, skill_entries: list[dict[str, Any]], root: Path | str | None = None):
        self.entries = skill_entries
        self.root = Path(root) if root else Path(__file__).parent.parent
        self.vectors: list[SkillVector] = []
        self._build()

    def _build(self) -> None:
        # 1. 分词 + 构建词汇表
        all_tokens: list[list[str]] = []
        self._entries_with_content: list[tuple[str, str, str]] = []  # (skill_id, name, content)
        for entry in self.entries:
            sid = entry.get("skill_id", "")
            name = entry.get("skill_name", "")
            # 尝试读取技能文件内容
            content = self._load_content(entry)
            tokens = _tokenize(content)
            all_tokens.append(tokens)
            self._entries_with_content.append((sid, name, content))

        # 2. 构建词汇表
        vocab = set()
        for tokens in all_tokens:
            vocab.update(tokens)
        if not vocab:
            return

        # 3. 计算 IDF
        idf = _compute_idf(all_tokens, vocab)

        # 4. 生成 TF-IDF 向量
        for i, (sid, name, content) in enumerate(self._entries_with_content):
            tokens = all_tokens[i]
            tfidf = _tfidf_vector(tokens, idf)
            self.vectors.append(SkillVector(skill_id=sid, skill_name=name, content=content, tfidf=tfidf))

    def _load_content(self, entry: dict[str, Any]) -> str:
        """从技能文件路径加载内容。"""
        skill_id = entry.get("skill_id", "")
        status = entry.get("status", "")
        if status == "draft":
            path = self.root / "skills" / "draft" / f"{skill_id}.md"
        elif status == "active":
            path = self.root / "skills" / "active" / f"{skill_id}.md"
        elif status == "archived":
            path = self.root / "skills" / "archived" / f"{skill_id}.md"
        else:
            return entry.get("skill_name", "")
        try:
            return path.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            return entry.get("skill_name", "")

    # ------------------------------------------------------------------
    # Pairwise similarity
    # ------------------------------------------------------------------

    SIMILARITY_MERGE_THRESHOLD = 0.60   # ≥ 0.60 → 建议合并
    SIMILARITY_REVIEW_THRESHOLD = 0.40  # 0.40 ~ 0.59 → 需人工审核

    def compute_pairwise(self) -> list[SimilarityResult]:
        """
        计算所有技能对的相似度。

        Returns:
            list[SimilarityResult]，按 score 降序排列。
        """
        results: list[SimilarityResult] = []
        n = len(self.vectors)
        for i in range(n):
            for j in range(i + 1, n):
                va, vb = self.vectors[i], self.vectors[j]
                content_sim = _cosine_sim(va.tfidf, vb.tfidf)
                name_sim = _name_similarity(va.skill_name, vb.skill_name)
                # 综合分数：内容为主，名称为辅
                score = 0.75 * content_sim + 0.25 * name_sim

                if score >= self.SIMILARITY_MERGE_THRESHOLD:
                    rec = "merge"
                elif score >= self.SIMILARITY_REVIEW_THRESHOLD:
                    rec = "review"
                else:
                    rec = "independent"

                results.append(SimilarityResult(
                    skill_a=va.skill_id,
                    skill_b=vb.skill_id,
                    score=round(score, 4),
                    name_sim=round(name_sim, 4),
                    content_sim=round(content_sim, 4),
                    recommendation=rec,
                ))
        results.sort(key=lambda x: x.score, reverse=True)
        return results

    def get_groups(self) -> list[list[str]]:
        """
        用连通分量将高相似度技能分组。
        阈值：SIMILARITY_MERGE_THRESHOLD
        """
        threshold = self.SIMILARITY_MERGE_THRESHOLD
        pairwise = self.compute_pairwise()
        # Build adjacency for pairs with score >= threshold
        adj: dict[str, set[str]] = {v.skill_id: set() for v in self.vectors}
        for r in pairwise:
            if r.score >= threshold:
                adj[r.skill_a].add(r.skill_b)
                adj[r.skill_b].add(r.skill_a)

        # Union-find via DFS
        visited: set[str] = set()
        groups: list[list[str]] = []

        def dfs(node: str, group: list[str]) -> None:
            visited.add(node)
            group.append(node)
            for nei in adj.get(node, []):
                if nei not in visited:
                    dfs(nei, group)

        for vec in self.vectors:
            if vec.skill_id not in visited:
                group: list[str] = []
                dfs(vec.skill_id, group)
                groups.append(group)

        return groups
