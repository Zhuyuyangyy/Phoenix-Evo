# -*- coding: utf-8 -*-
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger("skill_injection_policy")

MIN_INJECT_SCORE = 0.55
REPLAY_THRESHOLD = 2
REVIEW_THRESHOLD = 3
RISK_HIGH_BAN_THRESHOLD = 1

class InjectionDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REVIEW = "review"
    DEFER = "defer"

@dataclass
class InjectionRule:
    name: str
    passed: bool
    reason: str
    severity: str = "info"

@dataclass
class InjectionPolicyResult:
    skill_id: str
    skill_name: str
    decision: InjectionDecision
    rules: list = field(default_factory=list)
    final_reason: str = ""
    penalty: float = 0.0

    @property
    def is_allowed(self) -> bool:
        return self.decision == InjectionDecision.ALLOW

    @property
    def is_review_needed(self) -> bool:
        return self.decision == InjectionDecision.REVIEW

class SafeInjectionPolicy:
    def __init__(self): pass

    def evaluate(self, skill_entry: dict, skill_card: Optional[dict] = None,
                 task_type: Optional[str] = None, task_risk: str = "low",
                 consecutive_failures: int = 0, risk_events: int = 0,
                 evidence_score: float = 0.0) -> InjectionPolicyResult:
        skill_id = skill_entry.get("skill_id", "?")
        skill_name = skill_entry.get("skill_name", skill_entry.get("name", skill_id))
        rules = []
        decision = InjectionDecision.ALLOW
        final_reason = "passed all checks"
        penalty = 0.0

        status = skill_entry.get("status", "unknown")
        if status in ("quarantined", "archived", "deleted"):
            rules.append(InjectionRule("status_ban", False, f"status={status} -- hard block", "blocker"))
            return InjectionPolicyResult(skill_id, skill_name, InjectionDecision.DENY, rules, f"status={status}")

        if status in ("draft", "learning"):
            rules.append(InjectionRule("draft_require_review", False, f"status={status} -- must review", "blocker"))
            return InjectionPolicyResult(skill_id, skill_name, InjectionDecision.REVIEW, rules, f"status={status} requires review")

        rules.append(InjectionRule("status_ok", True, f"status={status}", "info"))

        if consecutive_failures >= REVIEW_THRESHOLD:
            rules.append(InjectionRule("consecutive_failure_review", False, f"cf={consecutive_failures}>={REVIEW_THRESHOLD}", "blocker"))
            return InjectionPolicyResult(skill_id, skill_name, InjectionDecision.REVIEW, rules, f"consecutive failures ({consecutive_failures})")

        if consecutive_failures >= REPLAY_THRESHOLD:
            rules.append(InjectionRule("consecutive_failure_warning", False, f"cf={consecutive_failures}>={REPLAY_THRESHOLD}", "warning"))
            if decision == InjectionDecision.ALLOW:
                decision = InjectionDecision.DEFER
                final_reason = f"consecutive failures ({consecutive_failures})"
            penalty += 0.3 * (consecutive_failures / REVIEW_THRESHOLD)
        else:
            rules.append(InjectionRule("consecutive_failure_ok", True, f"cf={consecutive_failures}<{REPLAY_THRESHOLD}", "info"))

        if risk_events >= RISK_HIGH_BAN_THRESHOLD and task_risk in ("high", "critical"):
            rules.append(InjectionRule("risk_event_ban", False, f"risk_events={risk_events}+task_risk={task_risk}", "blocker"))
            return InjectionPolicyResult(skill_id, skill_name, InjectionDecision.DENY, rules, f"risk event + high risk task")

        if evidence_score > 0 and evidence_score < MIN_INJECT_SCORE:
            rules.append(InjectionRule("evidence_score_ban", False, f"ev={evidence_score:.2f}<{MIN_INJECT_SCORE}", "blocker"))
            return InjectionPolicyResult(skill_id, skill_name, InjectionDecision.DENY, rules, f"evidence_score too low ({evidence_score:.2f})")

        rules.append(InjectionRule("evidence_score_ok", True,
            f"ev={evidence_score:.2f}>={MIN_INJECT_SCORE}" if evidence_score > 0 else "evidence_score not available", "info"))

        if task_type and task_type != "general":
            skill_tt = skill_entry.get("task_type", "")
            if skill_tt and skill_tt != task_type:
                rules.append(InjectionRule("task_type_mismatch", True, "penalty applied", "warning"))
                penalty += 0.3
            else:
                rules.append(InjectionRule("task_type_match", True, f"task_type={task_type} matches", "info"))

        if decision == InjectionDecision.ALLOW:
            if penalty >= 0.5:
                decision = InjectionDecision.DEFER
                final_reason = f"deferred (penalty={penalty:.2f})"
            elif penalty > 0:
                final_reason = f"allowed with penalty ({penalty:.2f})"

        return InjectionPolicyResult(skill_id, skill_name, decision, rules, final_reason, penalty)

    def filter_batch(self, skill_entries: list, skill_cards: Optional[dict] = None,
                     task_type: Optional[str] = None, task_risk: str = "low",
                     outcome_store: Optional[dict] = None) -> list:
        if outcome_store is None: outcome_store = {}
        results = []
        for entry in skill_entries:
            sid = entry.get("skill_id", "?")
            card = (skill_cards or {}).get(sid, {})
            outcome = outcome_store.get(sid, {})
            ie = entry.get("index_entry", {})
            result = self.evaluate(entry, card, task_type, task_risk,
                outcome.get("consecutive_failures", 0),
                outcome.get("risk_flags", 0),
                entry.get("evidence_score", ie.get("evidence_score", 0.0)))
            results.append(result)
        order = {InjectionDecision.ALLOW: 0, InjectionDecision.DEFER: 1, InjectionDecision.REVIEW: 2, InjectionDecision.DENY: 3}
        results.sort(key=lambda r: (order.get(r.decision, 99), -r.penalty))
        return results
