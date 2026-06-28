"""
skill_retriever: 技能检索器
V0.6 -- Phoenix-Evo Core Skill Retriever

职责：
  - 根据当前任务描述，从 skill_registry 检索 top-k 相似技能
  - 使用 sentence-embedding + 余弦相似度作为主要检索信号（V1.2 升级）
  - TF-IDF 作为 fallback（当 sentence-transformers 不可用时）
  - 对候选技能做预过滤（排除 quarantine / archived / rejected）
  - 返回 SkillRetrievalResult：ranked 列表 + 每条检索理由

V0.6 变更：
  - 删除独立的关键词匹配实现，改为复用 runtime/skill_retriever.py 的 TF-IDF 引擎
  - 保持 RetrievalMatch / SkillRetrievalResult 数据类接口不变

V1.2 变更（Q2 SCI Review Fix #1）：
  - 主检索引擎从 TF-IDF 升级为 sentence-embedding（all-MiniLM-L6-v2）
  - 解决 TF-IDF 无法捕捉改写语义相似性的问题
  - TF-IDF 保留为 fallback 路径
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Import TF-IDF engine from the runtime.tfidf_utils module (breaks circular import)
from runtime.tfidf_utils import (
    _compute_idf,
    _cosine_sim,
    _tfidf_vector,
    _tokenize,
    _tokenize_to_set,
)

# V1.2: Import semantic retriever for sentence-embedding-based search
try:
    from runtime.semantic_retriever import _EMBEDDING_AVAILABLE, SemanticRetriever
except ImportError:
    _EMBEDDING_AVAILABLE = False
    SemanticRetriever = None


# ----------------------------------------------------------------------
# RetrievalResult
# ----------------------------------------------------------------------

@dataclass
class RetrievalMatch:
    """单条检索结果。"""
    skill_id: str
    skill_name: str
    status: str                        # active / draft / quarantine
    similarity_score: float            # 0.0 ~ 1.0
    matched_keywords: list[str] = field(default_factory=list)
    matched_tags: list[str] = field(default_factory=list)
    evidence_score: float = 0.0        # evidence completeness (0.0 ~ 1.0)
    replay_pass_rate: float = 0.0      # 回放通过率
    replay_passed: bool | None = None  # 是否通过回放验证
    promotion_ready: bool = False      # 是否可以晋级
    risk_level: str = "low"
    source_trajectory: str = ""        # 来源轨迹 ID
    reason: str = ""                   # 为什么这条被召回


@dataclass
class SkillRetrievalResult:
    """
    完整检索结果。

    字段：
      task_goal        -- 原始任务描述
      top_k            -- 请求的 top-k
      total_candidates -- 召回前总数
      matches          -- 排序后的候选列表
      retrieval_time_ms -- 检索耗时
    """
    task_goal: str
    top_k: int
    total_candidates: int = 0
    matches: list[RetrievalMatch] = field(default_factory=list)
    retrieval_time_ms: float = 0.0


# ----------------------------------------------------------------------
# SkillRetriever
# ----------------------------------------------------------------------

class SkillRetriever:
    """
    任务驱动的技能检索器。

    检索策略（TF-IDF + 多维评分排序）：

    1. TF-IDF 文本匹配
       - 将 skill_name + task_goal + tags + inputs 拼接为文档
       - 使用 TF-IDF + 余弦相似度计算任务与技能的相关性

    2. 预过滤
       - 只召回 active + draft 技能
       - 排除 quarantine / archived / rejected

    3. 多维评分排序
       - tfidf_score × 0.40
       - evidence_score × 0.25         <- 有无证据卡
       - replay_score × 0.20           <- 回放是否通过
       - usage_score × 0.10            <- 使用频率（越高越好）
       - recency_score × 0.05         <- 最近使用时间

    4. 返回 top-k
    """

    TFIDF_WEIGHT = 0.40
    EVIDENCE_WEIGHT = 0.25
    REPLAY_WEIGHT = 0.20
    USAGE_WEIGHT = 0.10
    RECENCY_WEIGHT = 0.05

    # evidence/ 回放数据目录
    SKILL_CARDS_DIR = "evidence/skill_cards"
    REPLAY_REPORTS_DIR = "evidence/replay_reports"

    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root else Path(__file__).parent.parent
        self.skill_index_path = self.root / "skills" / "skill_index.json"
        self.cards_dir = self.root / self.SKILL_CARDS_DIR
        self.reports_dir = self.root / self.REPLAY_REPORTS_DIR

    def retrieve(
        self,
        task_goal: str,
        top_k: int = 5,
        status_filter: str | None = None,
    ) -> SkillRetrievalResult:
        """
        根据任务描述检索相关技能。

        Args:
            task_goal: 当前任务描述（自然语言）
            top_k: 返回 top-k 个候选
            status_filter: 可选，只召回指定状态的技能

        Returns:
            SkillRetrievalResult
        """
        import time
        t0 = time.monotonic()

        # Step 1: 加载 skill_index
        skill_index = self._load_skill_index()
        self.total_candidates = len(skill_index)

        # Step 2: 预过滤 + 构建 TF-IDF 语料库
        filtered: list[tuple[str, dict[str, Any]]] = []
        for skill_id, entry in skill_index.items():
            status = entry.get("status", "unknown")
            if status in ("quarantine", "archived", "rejected"):
                continue
            if status_filter and status != status_filter:
                continue
            filtered.append((skill_id, entry))

        if not filtered:
            return SkillRetrievalResult(
                task_goal=task_goal, top_k=top_k,
                total_candidates=len(skill_index), matches=[], retrieval_time_ms=0.0,
            )

        # Step 3: 构建语料库（query + 所有候选技能文档）
        corpus_texts = []
        for _sid, entry in filtered:
            corpus_texts.append(self._build_skill_text(entry))

        # Step 4: 计算每个候选的综合评分
        # V1.2: 使用 sentence-embedding 作为主要检索信号，TF-IDF 作为 fallback
        semantic_scores: dict[int, float] = {}
        if _EMBEDDING_AVAILABLE and SemanticRetriever is not None:
            sem_retriever = SemanticRetriever()
            sem_results = sem_retriever.retrieve(
                task_goal, corpus_texts, top_k=len(filtered), score_threshold=0.0,
            )
            semantic_scores = {r["index"]: r["score"] for r in sem_results}

        # Fallback: TF-IDF scores
        query_tokens = _tokenize(task_goal)
        corpus_tokens: list[list[str]] = [query_tokens]
        for text in corpus_texts:
            corpus_tokens.append(_tokenize(text))
        idf = _compute_idf(corpus_tokens)
        query_vec = _tfidf_vector(query_tokens, idf)
        tfidf_scores: dict[int, float] = {}
        for idx in range(len(filtered)):
            skill_vec = _tfidf_vector(corpus_tokens[idx + 1], idf)
            tfidf_scores[idx] = _cosine_sim(query_vec, skill_vec)

        candidates: list[RetrievalMatch] = []
        for idx, (skill_id, entry) in enumerate(filtered):
            # Primary: semantic embedding score; Fallback: TF-IDF
            text_score = semantic_scores.get(idx, 0.0) if semantic_scores else tfidf_scores.get(idx, 0.0)

            # Evidence Score（从 skill_card 读取）
            evidence_score = self._get_evidence_score(skill_id)

            # Replay Score（从 replay_report 读取）
            replay_info = self._get_replay_info(skill_id)

            # Usage Score（usage_count 归一化，5次以上满分）
            usage_count = entry.get("usage_count", 0)
            usage_score = min(usage_count / 5.0, 1.0)

            # Recency Score（30天内用过满分）
            recency_score = self._get_recency_score(entry.get("last_used"))

            # 综合评分 (V1.2: text_score 可以是 semantic 或 tfidf)
            overall = (
                text_score * self.TFIDF_WEIGHT
                + evidence_score * self.EVIDENCE_WEIGHT
                + replay_info["score"] * self.REPLAY_WEIGHT
                + usage_score * self.USAGE_WEIGHT
                + recency_score * self.RECENCY_WEIGHT
            )

            # 匹配的关键词（用于调试/展示）
            matched_kw = self._extract_matched_keywords(task_goal, entry)

            reason = self._build_reason(text_score, matched_kw, evidence_score, replay_info)

            candidates.append(RetrievalMatch(
                skill_id=skill_id,
                skill_name=entry.get("skill_name", ""),
                status=entry.get("status", "unknown"),
                similarity_score=round(overall, 4),
                matched_keywords=matched_kw,
                matched_tags=self._match_tags(task_goal, entry.get("tags", [])),
                evidence_score=round(evidence_score, 4),
                replay_pass_rate=replay_info["pass_rate"],
                replay_passed=replay_info["passed"],
                promotion_ready=entry.get("promotion_ready", False),
                risk_level=entry.get("risk_level", "low"),
                source_trajectory=entry.get("source_trajectory", ""),
                reason=reason,
            ))

        # Step 5: 排序
        candidates.sort(key=lambda x: x.similarity_score, reverse=True)

        elapsed_ms = (time.monotonic() - t0) * 1000
        return SkillRetrievalResult(
            task_goal=task_goal,
            top_k=top_k,
            total_candidates=len(skill_index),
            matches=candidates[:top_k],
            retrieval_time_ms=round(elapsed_ms, 2),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_skill_text(entry: dict[str, Any]) -> str:
        """将技能字段拼接为单个文本，用于 TF-IDF 向量化。"""
        parts: list[str] = [
            entry.get("skill_name", ""),
            entry.get("task_goal", ""),
            " ".join(entry.get("tags", [])),
            " ".join(entry.get("inputs", [])),
        ]
        return " ".join(p for p in parts if p)

    @staticmethod
    def _extract_matched_keywords(task_goal: str, entry: dict[str, Any]) -> list[str]:
        """提取任务与技能之间的重叠关键词。"""
        query_tokens = _tokenize_to_set(task_goal)
        skill_text = (
            entry.get("skill_name", "") + " "
            + entry.get("task_goal", "") + " "
            + " ".join(entry.get("tags", []))
        ).lower()
        skill_tokens = _tokenize_to_set(skill_text)
        return sorted(query_tokens & skill_tokens)

    def _get_evidence_score(self, skill_id: str) -> float:
        """从 skill_card 读取 evidence completeness score。"""
        card_path = self.cards_dir / f"{skill_id}.card.json"
        if not card_path.exists():
            return 0.0
        try:
            card = json.loads(card_path.read_text(encoding="utf-8"))
            score = 0.0
            if card.get("source_trajectory_ids"):
                score += 0.4
            if card.get("task_goal"):
                score += 0.2
            if card.get("verified_by"):
                score += 0.2
            if card.get("procedure_steps", 0) >= 3:
                score += 0.2
            return min(score, 1.0)
        except (OSError, json.JSONDecodeError):
            return 0.0

    def _get_replay_info(self, skill_id: str) -> dict[str, Any]:
        """从 replay_report 读取回放结果。"""
        reports_dir = self.reports_dir
        if not reports_dir.exists():
            return {"score": 0.0, "pass_rate": 0.0, "passed": None}

        report_files = sorted(reports_dir.glob(f"replay_{skill_id}_*.report.json"))
        if not report_files:
            return {"score": 0.0, "pass_rate": 0.0, "passed": None}

        try:
            report = json.loads(report_files[-1].read_text(encoding="utf-8"))
            pass_rate = report.get("passed_cases", 0) / max(report.get("total_cases", 1), 1)
            passed = report.get("overall_pass", False) if report.get("total_cases", 0) > 0 else None
            regression = report.get("regression_found", False)
            score = pass_rate if not regression else pass_rate * 0.2
            return {"score": round(score, 4), "pass_rate": round(pass_rate, 4), "passed": passed}
        except (OSError, json.JSONDecodeError):
            return {"score": 0.0, "pass_rate": 0.0, "passed": None}

    def _get_recency_score(self, last_used: str | None) -> float:
        """最近使用时间评分（30 天内满分）。"""
        if not last_used:
            return 0.3  # 从未使用，打折
        try:
            from datetime import datetime
            last = datetime.fromisoformat(last_used)
            age_days = (datetime.now() - last).total_seconds() / 86400
            return max(0.0, 1.0 - age_days / 30.0)
        except (ValueError, TypeError):
            return 0.3

    def _match_tags(self, task_goal: str, tags: list[str]) -> list[str]:
        """返回匹配的标签。"""
        query_tokens = _tokenize_to_set(task_goal)
        return [t for t in tags if t.lower() in query_tokens]

    def _load_skill_index(self) -> dict[str, Any]:
        if not self.skill_index_path.exists():
            return {}
        try:
            return json.loads(self.skill_index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _build_reason(
        self,
        tfidf_score: float,
        matched_kw: list[str],
        evidence_score: float,
        replay_info: dict[str, Any],
    ) -> str:
        parts = []
        if tfidf_score > 0.1:
            parts.append(f"TF-IDF 相似度 {tfidf_score:.2f}")
        if matched_kw:
            parts.append(f"关键词匹配 {len(matched_kw)} 个：{', '.join(matched_kw[:3])}")
        if evidence_score >= 0.6:
            parts.append(f"证据完整度 {evidence_score:.0%}")
        if replay_info["passed"] is True:
            parts.append("回放通过")
        elif replay_info["passed"] is False:
            parts.append("回放未通过")
        if not parts:
            parts.append("无明确匹配理由")
        return "; ".join(parts)
