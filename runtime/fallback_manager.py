"""FallbackManager: V0.6 Runtime Skill Router - Fallback when no skill matched or denied"""
from dataclasses import dataclass, field
from enum import Enum


class FallbackReason(Enum):
    NO_SKILL_FOUND = "no_skill_found"
    ALL_DENIED = "all_denied"
    DENIED = "denied"
    REVIEW_REQUIRED = "review_required"
    SKILL_EXECUTION_FAILED = "skill_execution_failed"
    GUARD_REVIEW = "guard_review"

@dataclass
class FallbackResult:
    use_skill: bool
    fallback_reason: FallbackReason
    context: str
    suggestions: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

class FallbackManager:
    def __init__(self, base_dir=None):
        self.base_dir = base_dir

    def get_fallback(self, task_description, reason, denied_skills=None,
                      review_skills=None, error_message=None):
        denied_skills = denied_skills or []
        review_skills = review_skills or []
        if reason == FallbackReason.NO_SKILL_FOUND:
            return self._fallback_no_skill(task_description)
        if reason in (FallbackReason.ALL_DENIED, FallbackReason.DENIED):
            return self._fallback_denied(task_description, denied_skills, error_message)
        if reason in (FallbackReason.GUARD_REVIEW, FallbackReason.REVIEW_REQUIRED):
            return self._fallback_review(task_description, review_skills)
        if reason == FallbackReason.SKILL_EXECUTION_FAILED:
            return self._fallback_execution_failed(task_description, error_message)
        return self._fallback_no_skill(task_description)

    @staticmethod
    def _fallback_no_skill(task_description):
        return FallbackResult(
            use_skill=False,
            fallback_reason=FallbackReason.NO_SKILL_FOUND,
            context=("[Skill Routing] No matching Phoenix active skills found. "
                     "Agent will proceed normally."),
            suggestions=["Check /skills for draft skills", "Use phoenix.skills.list() to view active skills"],
            metadata={"skill_count": 0, "injected": False},
        )

    @staticmethod
    def _fallback_denied(task_description, denied_skills, error_message):
        skill_list = ", ".join(denied_skills) if denied_skills else "N/A"
        extra = ""
        if error_message:
            extra = " Reason: " + str(error_message)
        ctx = "[Skill Routing] Candidate skills (" + skill_list + ") failed RuntimeGuard checks." + extra
        return FallbackResult(
            use_skill=False,
            fallback_reason=FallbackReason.DENIED,
            context=ctx,
            suggestions=["Denied skills: " + skill_list, "Use /skills to manually review and activate"],
            metadata={"skill_count": 0, "injected": False, "denied_skills": denied_skills},
        )

    @staticmethod
    def _fallback_review(task_description, review_skills):
        skill_list = ", ".join(review_skills) if review_skills else "N/A"
        ctx = "[Skill Routing] Candidate skills (" + skill_list + ") require human review before use."
        return FallbackResult(
            use_skill=False,
            fallback_reason=FallbackReason.REVIEW_REQUIRED,
            context=ctx,
            suggestions=["Review required: " + skill_list, "Use phoenix.skills.review(skill_id) to approve"],
            metadata={"skill_count": 0, "injected": False, "review_skills": review_skills},
        )

    @staticmethod
    def _fallback_execution_failed(task_description, error_message):
        extra = ""
        if error_message:
            extra = " Error: " + str(error_message)
        ctx = "[Skill Execution] Skill execution failed, falling back to baseline." + extra
        return FallbackResult(
            use_skill=False,
            fallback_reason=FallbackReason.SKILL_EXECUTION_FAILED,
            context=ctx,
            suggestions=["Failure recorded in Phoenix runtime reporter", "Consecutive failures >= 2 will trigger replay"],
            metadata={"skill_count": 0, "injected": False, "fallback_triggered": True},
        )
