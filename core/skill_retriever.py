"""
skill_retriever: 技能检索器
V0.5 — Phoenix-Evo Runtime Skill Router

职责：
  - 根据当前任务描述，从 skill_registry 检索 top-k 相似技能
  - 支持多路召回：关键词匹配 + 向量相似度 + 标签过滤
  - 对候选技能做预过滤（排除 quarantine / archived / rejected）
  - 返回 SkillRetrievalResult：ranked 列表 + 每条检索理由
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


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
      task_goal        — 原始任务描述
      top_k            — 请求的 top-k
      total_candidates — 召回前总数
      matches          — 排序后的候选列表
      retrieval_time_ms — 检索耗时
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

    V0.5 检索策略（多路召回 + 排序）：

    1. 文本匹配召回
       - skill_name + task_goal + tags + inputs 的关键词匹配
       - 正则提取关键词（英文 + 中文）

    2. 预过滤
       - 只召回 active + draft 技能
       - 排除 quarantine / archived / rejected

    3. 多维评分排序
       - keyword_score × 0.30
       - evidence_score × 0.25         ← 有无证据卡
       - replay_score × 0.25           ← 回放是否通过
       - usage_score × 0.10            ← 使用频率（越高越好）
       - recency_score × 0.10         ← 最近使用时间

    4. 返回 top-k
    """

    KEYWORD_WEIGHT = 0.30
    EVIDENCE_WEIGHT = 0.25
    REPLAY_WEIGHT = 0.25
    USAGE_WEIGHT = 0.10
    RECENCY_WEIGHT = 0.10

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

        # Step 2: 提取任务关键词
        keywords = self._extract_keywords(task_goal)

        # Step 3: 预过滤 + 多维评分
        candidates: list[RetrievalMatch] = []
        for skill_id, entry in skill_index.items():
            status = entry.get("status", "unknown")

            # 过滤不可复用状态
            if status in ("quarantine", "archived", "rejected"):
                continue
            if status_filter and status != status_filter:
                continue

            # 提取关键词匹配分
            skill_text = (
                entry.get("skill_name", "")
                + " "
                + entry.get("task_goal", "")
                + " "
                + str(entry.get("tags", []))
                + " "
                + str(entry.get("inputs", []))
            ).lower()

            matched_kw = [kw for kw in keywords if kw.lower() in skill_text]
            keyword_score = len(matched_kw) / len(keywords) if keywords else 0.0

            # Evidence Score（从 skill_card 读取）
            evidence_score = self._get_evidence_score(skill_id)

            # Replay Score（从 replay_report 读取）
            replay_info = self._get_replay_info(skill_id)

            # Usage Score（usage_count 归一化，5次以上满分）
            usage_count = entry.get("usage_count", 0)
            usage_score = min(usage_count / 5.0, 1.0)

            # Recency Score（30天内用过满分）
            recency_score = self._get_recency_score(entry.get("last_used"))

            # 综合评分
            overall = (
                keyword_score * self.KEYWORD_WEIGHT
                + evidence_score * self.EVIDENCE_WEIGHT
                + replay_info["score"] * self.REPLAY_WEIGHT
                + usage_score * self.USAGE_WEIGHT
                + recency_score * self.RECENCY_WEIGHT
            )

            reason = self._build_reason(keyword_score, matched_kw, evidence_score, replay_info)

            candidates.append(RetrievalMatch(
                skill_id=skill_id,
                skill_name=entry.get("skill_name", ""),
                status=status,
                similarity_score=round(overall, 4),
                matched_keywords=matched_kw,
                matched_tags=self._match_tags(keywords, entry.get("tags", [])),
                evidence_score=round(evidence_score, 4),
                replay_pass_rate=replay_info["pass_rate"],
                replay_passed=replay_info["passed"],
                promotion_ready=entry.get("promotion_ready", False),
                risk_level=entry.get("risk_level", "low"),
                source_trajectory=entry.get("source_trajectory", ""),
                reason=reason,
            ))

        # Step 4: 排序
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
    # Keyword extraction
    # ------------------------------------------------------------------

    def _extract_keywords(self, text: str) -> list[str]:
        """
        从任务描述提取关键词。
        策略：英文词（3+字符）+ 中文词（2+字符）
        """
        english = re.findall(r"[a-zA-Z_][a-zA-Z0-9_-]{2,}", text)
        chinese = re.findall(r"[\u4e00-\u9fff]{2,}", text)
        return english + chinese

    # ------------------------------------------------------------------
    # Evidence & Replay 读取
    # ------------------------------------------------------------------

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
        except (json.JSONDecodeError, IOError):
            return 0.0

    def _get_replay_info(self, skill_id: str) -> dict[str, Any]:
        """从 replay_report 读取回放结果。"""
        # 查找最新的 replay report
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
        except (json.JSONDecodeError, IOError):
            return {"score": 0.0, "pass_rate": 0.0, "passed": None}

    # ------------------------------------------------------------------
    # Usage / Recency
    # ------------------------------------------------------------------

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

    def _match_tags(self, keywords: list[str], tags: list[str]) -> list[str]:
        """返回匹配的标签。"""
        kw_lower = [k.lower() for k in keywords]
        return [t for t in tags if t.lower() in kw_lower]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_skill_index(self) -> dict[str, Any]:
        if not self.skill_index_path.exists():
            return {}
        try:
            return json.loads(self.skill_index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            return {}

    def _build_reason(
        self,
        keyword_score: float,
        matched_kw: list[str],
        evidence_score: float,
        replay_info: dict[str, Any],
    ) -> str:
        parts = []
        if matched_kw:
            parts.append(f"关键词匹配 {len(matched_kw)} 个：{', '.join(matched_kw[:3])}")
        if evidence_score >= 0.6:
            parts.append(f"证据完整度 {evidence_score:.0%}")
        if replay_info["passed"] is True:
            parts.append("回放通过")
        elif replay_info["passed"] is False:
            parts.append("⚠️ 回放未通过")
        if not parts:
            parts.append("无明确匹配理由")
        return "; ".join(parts)
