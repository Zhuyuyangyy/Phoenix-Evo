# -*- coding: utf-8 -*-
"""
RuntimeGuard: Runtime Security Gate
V0.6 - Phoenix-Evo Runtime Skill Router

V0.6 boundary rules:
  1. draft skill -> deny
  2. quarantine skill -> deny
  3. archived skill -> deny
  4. evidence_score < 0.60 -> deny
  5. risk_score > 0.50 -> deny
  6. replay_regression = true -> deny
  7. task_risk = critical + skill_risk != low -> deny
  8. high risk task + no replay -> review_required
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from runtime.skill_router import RouteResult


class GuardDecision(Enum):
    ALLOW = "allow"
    REVIEW = "review"
    DENY  = "deny"


@dataclass
class GuardResult:
    skill_id: str = ""
    skill_name: str = ""
    decision: GuardDecision = GuardDecision.DENY
    reason: str = ""
    blocked_rules: list[str] = field(default_factory=list)
    passed_rules: list[str] = field(default_factory=list)
    needs_review: bool = False

    @property
    def can_inject(self) -> bool:
        return self.decision == GuardDecision.ALLOW

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["decision"] = self.decision.value
        return d


class RuntimeGuard:
    EVIDENCE_THRESHOLD = 0.60
    RISK_SCORE_THRESHOLD = 0.50

    def check(self, route_result: "RouteResult", task_risk: str = "low") -> GuardResult:
        result = GuardResult(
            skill_id=route_result.skill_id,
            skill_name=route_result.skill_name,
        )

        evidence      = getattr(route_result, "evidence_score", 0.0)
        risk_score    = getattr(route_result, "risk_score", 0.0)
        risk_level    = getattr(route_result, "risk_level", "unknown")
        replay_passed      = getattr(route_result, "replay_passed", None)
        replay_regression  = getattr(route_result, "replay_regression", False)
        route_decision    = getattr(route_result, "route_decision", None)

        # Router DENY takes priority
        if route_decision is not None:
            try:
                from runtime.skill_router import RouteDecision as RD
                if route_decision == RD.DENY:
                    result.decision = GuardDecision.DENY
                    result.reason = "RouterDecision.DENY"
                    result.blocked_rules.append("router_deny")
                    return result
            except Exception:
                pass

        # evidence check
        if evidence < self.EVIDENCE_THRESHOLD:
            result.decision = GuardDecision.DENY
            result.blocked_rules.append("evidence_below_threshold")
            result.reason = "evidence_score {:.0%} < {:.0%}".format(
                evidence, self.EVIDENCE_THRESHOLD)
            return result
        result.passed_rules.append("evidence_ok")

        # risk check
        if risk_score > self.RISK_SCORE_THRESHOLD:
            result.decision = GuardDecision.DENY
            result.blocked_rules.append("risk_above_threshold")
            result.reason = "risk_score {:.2f} > {:.2f}".format(
                risk_score, self.RISK_SCORE_THRESHOLD)
            return result
        result.passed_rules.append("risk_ok")

        # regression check
        if replay_regression is True:
            result.decision = GuardDecision.DENY
            result.blocked_rules.append("replay_regression")
            result.reason = "replay regression detected"
            return result
        result.passed_rules.append("no_regression")

        # critical task + non-low skill risk
        if task_risk == "critical" and risk_level not in ("none", "low"):
            result.decision = GuardDecision.DENY
            result.blocked_rules.append("critical_task_high_skill_risk")
            result.reason = "critical task + {} skill risk".format(risk_level)
            return result
        result.passed_rules.append("task_risk_compatible")

        # high/critical task + no replay
        if task_risk in ("high", "critical") and replay_passed is not True:
            result.decision = GuardDecision.REVIEW
            result.needs_review = True
            result.reason = "high risk task without replay verification"
            return result

        result.decision = GuardDecision.ALLOW
        result.reason = "passed all guards"
        return result

    def check_multiple(self, results: list["RouteResult"], task_risk: str = "low") -> list[GuardResult]:
        return [self.check(r, task_risk) for r in results]

    def format_summary(self, results: list[GuardResult]) -> str:
        allowed = [r for r in results if r.decision == GuardDecision.ALLOW]
        review  = [r for r in results if r.decision == GuardDecision.REVIEW]
        denied  = [r for r in results if r.decision == GuardDecision.DENY]
        parts = [
            "[RuntimeGuard] checked {} skills".format(len(results)),
            "  ALLOW: {}, REVIEW: {}, DENY: {}".format(
                len(allowed), len(review), len(denied)),
        ]
        for r in denied:
            parts.append("  [{}] {}: {}".format(r.skill_id, r.skill_name, r.reason))
        return chr(10).join(parts)
