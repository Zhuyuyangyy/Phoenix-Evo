"""
Phoenix-Evo V0.5 Integration Policy
集成权限与安全策略：限制 Phoenix → Hermes 的操作边界。

V0.5 约束核心原则：
- Phoenix 只能生成 draft skill
- 禁止自动激活 skill
- 禁止自动调用 skill
- 禁止覆盖/修改 Hermes 系统 skill
- 高风险 trajectory 不生成 skill
- quarantine skill 不导出到 Hermes

本模块定义了所有集成约束检查，供 Bridge 和 Exporter 调用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class IntegrationPermission(Enum):
    """V0.5 权限枚举。"""
    # 读操作
    READ_SKILLS = "read_skills"           # 读取 Hermes skills
    READ_TRAJECTORY = "read_trajectory"   # 读取轨迹历史

    # 写操作
    WRITE_DRAFT = "write_draft"           # 写入 Phoenix draft（always ok）
    EXPORT_DRAFT = "export_draft"         # 导出 draft 到 Hermes
    REQUEST_ACTIVATE = "request_activate" # 申请激活（V0.5 禁止）
    AUTO_CALL_SKILL = "auto_call_skill"    # 自动调用 skill（禁止）

    # 高危操作
    DELETE_SKILL = "delete_skill"          # 删除 skill（禁止）
    MODIFY_HERMES_SYSTEM = "modify_hermes_system"  # 修改 Hermes 系统文件（禁止）
    OVERRIDE_SKILL = "override_skill"      # 覆盖已有 skill（禁止）


@dataclass
class IntegrationPolicy:
    """
    V0.5 集成策略配置。
    所有检查基于此配置。
    """

    # 基础约束
    allow_auto_activation: bool = False        # V0.5 禁止自动激活
    allow_auto_call_skill: bool = False       # V0.5 禁止自动调用
    allow_override_hermes_skill: bool = False # 禁止覆盖 Hermes skill
    allow_delete_skill: bool = False          # 禁止删除 skill
    allow_modify_hermes_system: bool = False  # 禁止修改 Hermes 系统文件

    # 导出约束
    export_only_drafts: bool = True           # V0.5 只导出 draft
    require_manual_review_before_export: bool = True  # 导出前需人工复核
    quarantine_export_requires_review: bool = True    # quarantine 导出必须人工确认

    # 高风险轨迹过滤
    high_risk_types: frozenset[str] = field(default_factory=lambda: frozenset([
        "payment", "auth_bypass", "penetration",
        "data_destruction", "privacy_steal",
    ]))
    high_risk_level: str = "high"

    # 允许的任务类型（白名单）
    allowed_task_types: frozenset[str] = field(default_factory=lambda: frozenset([
        "coding", "writing", "research", "planning",
        "debugging", "analysis", "general",
    ]))

    @classmethod
    def strict(cls) -> IntegrationPolicy:
        """最严格策略（V0.5 默认）。"""
        return cls(
            allow_auto_activation=False,
            allow_auto_call_skill=False,
            allow_override_hermes_skill=False,
            allow_delete_skill=False,
            allow_modify_hermes_system=False,
            export_only_drafts=True,
            require_manual_review_before_export=True,
            quarantine_export_requires_review=True,
        )

    @classmethod
    def permissive(cls) -> IntegrationPolicy:
        """宽松策略（仅供测试）。"""
        return cls(
            allow_auto_activation=False,
            allow_auto_call_skill=False,
            allow_override_hermes_skill=True,
            allow_delete_skill=False,
            allow_modify_hermes_system=False,
            export_only_drafts=False,
            require_manual_review_before_export=False,
            quarantine_export_requires_review=True,
        )


class PolicyChecker:
    """
    策略检查器。
    供 Bridge 和 Exporter 调用，检查操作是否合规。
    """

    def __init__(self, policy: IntegrationPolicy | None = None):
        self.policy = policy or IntegrationPolicy.strict()

    def can_auto_activate(self) -> bool:
        """是否允许自动激活 skill。"""
        return self.policy.allow_auto_activation

    def can_auto_call_skill(self) -> bool:
        """是否允许自动调用 skill。"""
        return self.policy.allow_auto_call_skill

    def can_export_skill(
        self,
        skill_status: str,
        evidence_score: float = 0.0,
    ) -> tuple[bool, str]:
        """
        检查是否允许导出 skill 到 Hermes。

        Args:
            skill_status: Phoenix skill 状态（draft/active/quarantine/reject）
            evidence_score: 证据分（0-1）

        Returns:
            (allowed, reason)
        """
        # reject 状态禁止导出
        if skill_status == "reject":
            return False, "reject 状态 skill 禁止导出"

        # quarantine 状态需要人工复核
        if skill_status == "quarantine":
            if self.policy.quarantine_export_requires_review:
                return False, "quarantine 状态需要人工复核后才可导出"
            return True, "ok"

        # active 状态（V0.5 不导出 active）
        if skill_status == "active":
            return False, "active 状态 skill 不在导出范围（V0.5 仅导出 draft）"

        # draft 状态
        if skill_status == "draft":
            if self.policy.require_manual_review_before_export and evidence_score < 0.7:
                return False, f"draft skill 证据分 {evidence_score:.2f} < 0.7，需人工复核"
            return True, "ok"

        return False, f"未知 skill 状态: {skill_status}"

    def can_override_hermes_skill(
        self,
        hermes_skill_exists: bool,
        overwrite_requested: bool = False,
    ) -> tuple[bool, str]:
        """
        检查是否允许覆盖 Hermes 已有的 skill。

        Args:
            hermes_skill_exists: Hermes 目标路径是否已有 skill
            overwrite_requested: 调用方是否明确请求覆盖

        Returns:
            (allowed, reason)
        """
        if not hermes_skill_exists:
            return True, "目标不存在，可写入"

        if not self.policy.allow_override_hermes_skill:
            return False, "禁止覆盖 Hermes skill（overwrite 未授权）"

        if not overwrite_requested:
            return False, "需要显式设置 overwrite=True 才能覆盖"

        return True, "ok"

    def is_high_risk_trajectory(
        self,
        task_type: str = "",
        risk_level: str = "",
        task_goal: str = "",
    ) -> tuple[bool, str]:
        """
        检查轨迹是否高风险（高风险轨迹不生成 skill）。

        Args:
            task_type: 任务类型
            risk_level: Hermes 指定的风险等级
            task_goal: 任务目标描述

        Returns:
            (is_high_risk, reason)
        """
        # 检查 Hermes risk_level
        if risk_level == self.policy.high_risk_level:
            return True, f"Hermes 指定 risk_level={risk_level}"

        # 检查任务类型白名单
        if self.policy.allowed_task_types and task_type and task_type not in self.policy.allowed_task_types:
            return True, f"任务类型 {task_type} 不在白名单"

        # 检查危险关键词（简单正则）
        dangerous_keywords = [
            "rm -rf", "drop table", "truncate", "delete all",
            "sudo rm", "绕过", "bypass", "密码", "password",
            "注入", "inject", "伪造", "fake",
        ]
        goal_lower = task_goal.lower()
        for kw in dangerous_keywords:
            if kw.lower() in goal_lower:
                return True, f"任务目标包含危险关键词: {kw}"

        return False, "ok"

    def check_permission(
        self,
        permission: IntegrationPermission,
    ) -> tuple[bool, str]:
        """
        检查指定权限是否允许。

        Args:
            permission: IntegrationPermission 枚举值

        Returns:
            (allowed, reason)
        """
        if permission == IntegrationPermission.WRITE_DRAFT:
            return True, "draft 写入始终允许"

        if permission == IntegrationPermission.READ_SKILLS:
            return True, "读取 Hermes skills 允许"

        if permission == IntegrationPermission.READ_TRAJECTORY:
            return True, "读取轨迹历史允许"

        if permission == IntegrationPermission.EXPORT_DRAFT:
            return self.can_export_skill(skill_status="draft")

        if permission == IntegrationPermission.REQUEST_ACTIVATE:
            if not self.policy.allow_auto_activation:
                return False, "V0.5 禁止自动激活 skill"
            return True, "ok"

        if permission == IntegrationPermission.AUTO_CALL_SKILL:
            if not self.policy.allow_auto_call_skill:
                return False, "V0.5 禁止自动调用 skill"
            return True, "ok"

        if permission == IntegrationPermission.DELETE_SKILL:
            return False, "V0.5 禁止删除 skill"

        if permission == IntegrationPermission.MODIFY_HERMES_SYSTEM:
            return False, "V0.5 禁止修改 Hermes 系统文件"

        if permission == IntegrationPermission.OVERRIDE_SKILL:
            return self.can_override_hermes_skill(
                hermes_skill_exists=True,
                overwrite_requested=False,
            )

        return False, f"未知权限: {permission}"


# 全局默认检查器（V0.5 严格策略）
_default_checker: PolicyChecker | None = None


def get_checker(policy: IntegrationPolicy | None = None) -> PolicyChecker:
    """获取策略检查器。"""
    global _default_checker
    if policy is not None:
        return PolicyChecker(policy)
    if _default_checker is None:
        _default_checker = PolicyChecker(IntegrationPolicy.strict())
    return _default_checker
