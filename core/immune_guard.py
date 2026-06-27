"""ImmuneGuard: Phoenix-Evo V0.2 免疫防御层"""

import re
from dataclasses import dataclass
from pathlib import Path

from .immune_memory import ImmuneMemory
from .quarantine_manager import QuarantineManager
from .risk_policy import (
    DANGEROUS_PATTERNS,
    IMMUNE_DECISION,
    MEDIUM_RISK_TAGS,
    RiskPolicy,
    RiskProfile,
)


@dataclass
class ImmuneDecision:
    decision: IMMUNE_DECISION
    risk_profile: RiskProfile
    immune_rules_triggered: list[str]
    reason: str


class ImmuneGuard:
    def __init__(self, root=None):
        if root is None:
            self.root = Path(__file__).parent.parent
        elif isinstance(root, str):
            self.root = Path(root)
        else:
            self.root = root
        self.policy = RiskPolicy()
        self.immune_memory = ImmuneMemory(root=self.root)
        self.quarantine_mgr = QuarantineManager(root=self.root)

    def examine(self, skill_candidate, trajectory, verification_result):
        profile = self._build_profile(skill_candidate, trajectory, verification_result)
        profile = self.policy.evaluate(profile)
        profile = self.policy.compute_decision(profile)
        decision = profile.immune_decision
        immune_rules = self._rules_triggered(profile)
        if decision in ('quarantine', 'reject') and profile.has_high_risk_tag:
            self.immune_memory.record_failure(
                skill_name=skill_candidate.get('skill_name', ''),
                reason=', '.join(immune_rules),
                tags=profile.tags,
            )
        reason = self._build_reason(decision, profile, immune_rules)
        return ImmuneDecision(decision, profile, immune_rules, reason)

    def _build_profile(self, skill_candidate, trajectory, verification_result):
        profile = RiskProfile()
        skill_md = skill_candidate.get('skill_md', '')
        found_patterns = []
        found_tags = []
        for category, _desc, keywords in DANGEROUS_PATTERNS:
            if any(kw in skill_md for kw in keywords):
                found_patterns.append(category)
                found_tags.append(category)
        profile.dangerous_patterns_found = found_patterns
        profile.tags = found_tags
        if profile.has_high_risk_tag:
            profile.risk_level = 'critical'
        elif found_patterns:
            profile.risk_level = 'high'
        elif set(found_tags) & MEDIUM_RISK_TAGS:
            profile.risk_level = 'medium'
        profile.source_failed = not trajectory.get('success', True)
        profile.has_trajectory_id = bool(trajectory.get('task_id'))
        profile.has_artifacts = bool(trajectory.get('artifacts'))
        profile.has_verification = self._has_verification_steps(skill_md)
        profile.procedure_step_count = self._count_procedure_steps(skill_md)
        goal = trajectory.get('task_goal', '')
        profile.goal_length = len(goal.split())
        profile.similar_skill_failures = self.immune_memory.get_failure_count(
            skill_name=skill_candidate.get('skill_name', ''),
            tags=found_tags,
        )
        return profile

    def _has_verification_steps(self, skill_md):
        pattern = re.compile(
            r'^##\s+(Validation|Verification|验证)\b.*?(?=^##\s+|$)',
            re.MULTILINE | re.DOTALL,
        )
        for match in pattern.finditer(skill_md):
            body = match.group(0)
            lines_body = body.split('\n')[1:]
            if any(l.strip() for l in lines_body):
                return True
        return False

    def _count_procedure_steps(self, skill_md):
        proc_match = re.search(r'^##\s+Procedure\s*$', skill_md, re.MULTILINE)
        if not proc_match:
            return 0
        start = proc_match.end()
        next_sec = re.search(r'^##\s+', skill_md[start:], re.MULTILINE)
        end = start + next_sec.start() if next_sec else len(skill_md)
        proc_text = skill_md[start:end]
        steps = re.findall(r'(?m)^\s*(?:\d+\.\s+|-\s*\d+\.\s+)', proc_text)
        return len(steps)

    def _rules_triggered(self, profile):
        rules = []
        if profile.has_high_risk_tag:
            rules.append('HIGH_RISK_TAG')
        if profile.dangerous_patterns_found:
            rules.append('DANGEROUS_PATTERN')
        if profile.overgeneralized:
            rules.append('OVERGENERALIZED')
        if profile.source_failed and not profile.evidence_complete:
            rules.append('FAILED_SOURCE_NO_EVIDENCE')
        if profile.source_failed and not profile.has_verification:
            rules.append('FAILED_SOURCE_NO_VERIFICATION')
        if not profile.evidence_complete:
            rules.append('INCOMPLETE_EVIDENCE')
        if profile.similar_skill_failures >= 3:
            rules.append('REPEAT_FAILURE')
        if profile.has_medium_risk_tag:
            rules.append('MEDIUM_RISK_TAG')
        if not profile.has_artifacts:
            rules.append('MISSING_ARTIFACTS')
        return rules

    def _build_reason(self, decision, profile, rules):
        if decision == 'reject':
            return f"免疫拒绝：高危风险（{rules}），禁止入库"
        if decision == 'quarantine':
            return f"免疫隔离：待人工复核（触发规则: {rules}）"
        if profile.warnings:
            return f"免疫放行：进入 draft（{profile.warnings}）"
        return "免疫放行：进入 draft"
