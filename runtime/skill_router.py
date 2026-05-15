"""
SkillRouter: 从候选 skills 中综合排序选出最合适的技能
V0.6 - Phoenix-Evo Runtime Skill Router

排序公式：
  route_score =
    0.35 * similarity       (task_description 与 skill 的相关度)
  + 0.30 * evidence_score   (EvidenceSummary 综合分)
  + 0.20 * replay_pass_rate (Replay 回放通过率)
  + 0.15 * runtime_success_rate (历史使用成功率)
  - 0.30 * risk_score       (风险惩罚)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from runtime.skill_retriever import SkillRetriever


class RouteDecision(Enum):
    ALLOW = "allow"          # 允许注入 Hermes 上下文
    SUGGEST = "suggest"      # 仅建议（证据分/成功率偏低）
    DENY = "deny"            # 拒绝


@dataclass
class RouteResult:
    skill_id: str
    skill_name: str
    route_decision: RouteDecision
    route_score: float
    breakdown: dict[str, float] = field(default_factory=dict)
    reason: str = ""
    # 子维度（用于 debugger / 报告）
    similarity: float = 0.0
    evidence_score: float = 0.0
    replay_pass_rate: float = 0.0
    runtime_success_rate: float = 0.0
    risk_score: float = 0.0


class SkillRouter:
    """
    综合相似度、证据分、replay 表现、运行时成功率、风险分
    计算最终 route_score，并给出 RouteDecision。
    """

    # 路由决策阈值
    ALLOW_THRESHOLD  = 0.60   # route_score >= 0.60 → ALLOW
    SUGGEST_THRESHOLD = 0.40  # 0.40 <= score < 0.60 → SUGGEST

    # 权重
    W_SIMILARITY    = 0.35
    W_EVIDENCE      = 0.30
    W_REPLAY        = 0.20
    W_RUNTIME       = 0.15
    W_RISK_PENALTY  = 0.30

    def __init__(self, base_dir: str | None = None):
        self.retriever = SkillRetriever(base_dir=base_dir)

    # ------------------------------------------------------------------ #
    # 公开接口                                                          #
    # ------------------------------------------------------------------ #

    def route(
        self,
        task_description: str,
        task_type: str | None = None,
        risk_level: str | None = None,
        max_results: int = 3,
    ) -> list[RouteResult]:
        """
        主路由入口。

        参数:
            task_description: 任务描述
            task_type:        任务类型
            risk_level:        当前任务风险等级
            max_results:       最多返回几条路由结果（默认 3）

        返回:
            按 route_score 降序排列的 RouteResult 列表
        """
        # 1. 检索候选 skills
        candidates = self.retriever.retrieve(
            task_description=task_description,
            task_type=task_type,
            risk_level=risk_level,
            top_k=max_results * 2,  # 多取一些，过 Guard 会淘汰
        )

        if not candidates:
            return []

        # 2. 逐条计算 route_score
        results: list[RouteResult] = []
        for cand in candidates:
            route = self._score_skill(cand, risk_level=risk_level)
            results.append(route)

        # 3. 过滤 DENY，按 score 降序
        results.sort(key=lambda x: x.route_score, reverse=True)
        return results[:max_results]

    # ------------------------------------------------------------------ #
    # 内部实现                                                          #
    # ------------------------------------------------------------------ #

    def _score_skill(
        self,
        candidate: dict[str, Any],
        risk_level: str | None,
    ) -> RouteResult:
        entry = candidate["index_entry"]
        card  = candidate["skill_card"]
        skill_id = candidate["skill_id"]

        # ---- 提取各维度分数 ----
        similarity       = candidate["relevance_score"]
        evidence_score  = self._get_evidence_score(entry, card)
        replay_rate     = self._get_replay_pass_rate(entry)
        runtime_rate    = self._get_runtime_success_rate(entry)
        risk_score      = self._get_risk_score(entry, card, risk_level)

        # ---- 加权求和 ----
        raw_score = (
            self.W_SIMILARITY    * similarity
            + self.W_EVIDENCE    * evidence_score
            + self.W_REPLAY      * replay_rate
            + self.W_RUNTIME     * runtime_rate
            - self.W_RISK_PENALTY * risk_score
        )
        route_score = max(0.0, min(1.0, raw_score))

        # ---- 决策 ----
        if route_score >= self.ALLOW_THRESHOLD:
            decision = RouteDecision.ALLOW
            reason = "route_score >= 0.60，允许注入上下文"
        elif route_score >= self.SUGGEST_THRESHOLD:
            decision = RouteDecision.SUGGEST
            reason = f"route_score {route_score:.3f} 在 0.40~0.60 之间，仅建议使用"
        else:
            decision = RouteDecision.DENY
            reason = f"route_score {route_score:.3f} < 0.40，拒绝注入"

        return RouteResult(
            skill_id=skill_id,
            skill_name=candidate["skill_name"],
            route_decision=decision,
            route_score=round(route_score, 4),
            breakdown={
                "similarity":    round(similarity, 3),
                "evidence_score": round(evidence_score, 3),
                "replay_rate":    round(replay_rate, 3),
                "runtime_rate":  round(runtime_rate, 3),
                "risk_score":     round(risk_score, 3),
            },
            reason=reason,
            similarity=similarity,
            evidence_score=evidence_score,
            replay_pass_rate=replay_rate,
            runtime_success_rate=runtime_rate,
            risk_score=risk_score,
        )

    # ------------------------------------------------------------------ #
    # 分数提取工具（适配 Phoenix 多种版本 skill_index 字段）              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _get_evidence_score(entry: dict, card: dict) -> float:
        """
        从 index_entry 或 card 中提取 evidence_score。
        Phoenix V0.1-V0.4 字段名可能不同，做兼容。
        """
        # 直接字段
        for key in ("evidence_score", "evidence_summary_score", "quality_score",
                    "confidence", "replay_confidence"):
            if entry.get(key) is not None:
                val = float(entry[key])
                if 0 <= val <= 1:
                    return val
        # card 内的 evidence section
        ev = card.get("evidence", "") or card.get("evidence_summary", "")
        import re
        m = re.search(r"(\d+\.?\d*)\s*/\s*1", ev)
        if m:
            return min(1.0, float(m.group(1)))
        return 0.50  # 无数据返回中性分

    @staticmethod
    def _get_replay_pass_rate(entry: dict) -> float:
        """从 index_entry 提取 replay 通过率"""
        # V0.4 replay 结果
        for key in ("replay_pass_rate", "replay_success_rate", "replay_rate"):
            if entry.get(key) is not None:
                return max(0.0, min(1.0, float(entry[key])))
        # V0.4 replay_history 列表
        replay_hist = entry.get("replay_history", [])
        if isinstance(replay_hist, list) and replay_hist:
            passed = sum(1 for r in replay_hist if r.get("passed"))
            return passed / len(replay_hist)
        return 0.50  # 无数据返回中性分

    @staticmethod
    def _get_runtime_success_rate(entry: dict) -> float:
        """从 index_entry 提取 runtime 使用成功率"""
        rate = entry.get("success_rate") or entry.get("runtime_success_rate")
        if rate is not None:
            return max(0.0, min(1.0, float(rate)))
        usage = entry.get("usage_count", 0)
        if usage == 0:
            return 0.50  # 从未使用过的 skill 返回中性分
        # 有使用记录但无成功率
        successes = entry.get("success_count", 0)
        return successes / usage if usage > 0 else 0.50

    @staticmethod
    def _get_risk_score(
        entry: dict,
        card: dict,
        task_risk_level: str | None,
    ) -> float:
        """
        计算风险分（0.0~1.0，越高越危险）。
        来源：
          1. skill 内置 risk_score（index_entry.risk_level）
          2. skill_card risk_tags
          3. 当前任务 risk_level
        """
        score = 0.0

        # index_entry risk_level
        risk_map = {"low": 0.0, "medium": 0.30, "high": 0.60, "critical": 1.0}
        entry_risk = entry.get("risk_level", "")
        if entry_risk in risk_map:
            score = max(score, risk_map[entry_risk])

        # card risk_tags
        tags: list[str] = []
        if isinstance(card.get("risk_tags"), list):
            tags = card["risk_tags"]
        else:
            import re
            safety = card.get("safety note", "")
            tags = re.findall(r"\[([^\]]+)\]", safety)

        dangerous_keywords = ["sudo", "rm", "drop", "delete", "kill", "shutdown",
                               "grant", "priv", "exec", "inject", "format"]
        if any(t.lower() in dangerous_keywords for t in tags):
            score = max(score, 0.60)

        # task risk_level 与 skill risk_level 的冲突
        if task_risk_level:
            if task_risk_level.lower() == "low" and entry_risk in ("high", "critical"):
                score = max(score, 0.70)
            if task_risk_level.lower() == "high" and entry_risk == "low":
                score = max(score, 0.10)

        return min(1.0, score)
