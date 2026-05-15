"""
drift_detector: 技能漂移检测模块
V0.3 — Phoenix-Evo Curator

职责：
  - 检测技能行为是否偏离原始规范（成功率漂移 / 风险漂移 / 内容漂移）
  - 追踪技能历次修订历史，计算漂移幅度
  - 输出风险级别：stable / warning / drift / critical
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


# ----------------------------------------------------------------------
# Data structures
# ----------------------------------------------------------------------

@dataclass
class DriftRecord:
    """单次漂移记录。"""
    skill_id: str = ""
    drift_type: str = ""        # "success_rate" | "risk_level" | "content" | "usage"
    drift_direction: str = ""   # "up" | "down" | "changed"
    drift_score: float = 0.0    # 0.0 ~ 1.0，越大漂移越严重
    previous_value: Any = None
    current_value: Any = None
    severity: str = ""          # "stable" | "warning" | "drift" | "critical"
    detected_at: str = ""
    reason: str = ""


@dataclass
class SkillHealthReport:
    """技能健康报告。"""
    skill_id: str
    skill_name: str
    overall_severity: str        # "stable" | "warning" | "drift" | "critical"
    drift_records: list[DriftRecord] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    analyzed_at: str = ""


# ----------------------------------------------------------------------
# Thresholds (can be overridden)
# ----------------------------------------------------------------------
STALENESS_DAYS = 30            # 超过 N 天未使用 → stale
SUCCESS_RATE_WARNING = 0.70     # 成功率低于此值 → warning
SUCCESS_RATE_CRITICAL = 0.50    # 成功率低于此值 → critical
USAGE_COUNT_CRITICAL = 10       # 使用次数低于此值且stale → critical
RISK_LEVEL_INCREASE_WEIGHT = 0.3  # 风险等级每升一级增加的惩罚因子
MIN_USAGE_FOR_DRIFT = 3         # 至少需要 N 次使用记录才能判断成功率漂移


# ----------------------------------------------------------------------
# DriftDetector
# ----------------------------------------------------------------------

class DriftDetector:
    """
    检测技能库中技能的各类漂移。
    
    检测维度：
      1. 成功率漂移：usage_count 足够时，比较历史成功率是否持续下降
      2. 风险等级漂移：技能的风险等级是否比初始版本提高
      3. 使用频率异常：技能是否长期未使用（stale）
      4. 快速降级：短期内连续失败（连续失败数 >= 3）
    """

    def __init__(self, skill_index: dict[str, Any]):
        """
        Args:
            skill_index: skill_registry.get_index() 的返回值
        """
        self.index = skill_index
        self.records: list[DriftRecord] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_all(self) -> list[SkillHealthReport]:
        """
        分析所有 active / draft 技能的健康状况。
        
        Returns:
            list[SkillHealthReport]，包含每条技能的漂移记录和健康评级。
        """
        reports: list[SkillHealthReport] = []
        for skill_id, entry in self.index.items():
            status = entry.get("status", "")
            if status not in ("active", "draft"):
                continue
            report = self.analyze_skill(skill_id, entry)
            reports.append(report)
        # 按严重程度降序排列
        severity_order = {"critical": 0, "drift": 1, "warning": 2, "stable": 3}
        reports.sort(key=lambda r: severity_order.get(r.overall_severity, 3))
        return reports

    def analyze_skill(self, skill_id: str, entry: dict[str, Any]) -> SkillHealthReport:
        """
        分析单个技能的健康状况。
        """
        skill_name = entry.get("skill_name", skill_id)
        records: list[DriftRecord] = []

        # 1. 成功率漂移
        sr_record = self._check_success_rate(skill_id, entry)
        if sr_record:
            records.append(sr_record)

        # 2. 风险等级漂移
        risk_record = self._check_risk_drift(skill_id, entry)
        if risk_record:
            records.append(risk_record)

        # 3. 使用频率异常（stale）
        stale_record = self._check_staleness(skill_id, entry)
        if stale_record:
            records.append(stale_record)

        # 4. 快速连续失败
        fail_record = self._check_rapid_failure(skill_id, entry)
        if fail_record:
            records.append(fail_record)

        # 综合评级
        severity = self._overall_severity(records)
        recommendations = self._make_recommendations(records, severity, entry)

        return SkillHealthReport(
            skill_id=skill_id,
            skill_name=skill_name,
            overall_severity=severity,
            drift_records=records,
            recommendations=recommendations,
            analyzed_at=datetime.now().isoformat(),
        )

    # ------------------------------------------------------------------
    # Individual drift checks
    # ------------------------------------------------------------------

    def _check_success_rate(self, skill_id: str, entry: dict[str, Any]) -> DriftRecord | None:
        """
        检查成功率是否持续下降。
        逻辑：如果 usage_count 足够且 success_rate 低于阈值，标记漂移。
        """
        usage_count = entry.get("usage_count", 0)
        if usage_count < MIN_USAGE_FOR_DRIFT:
            return None

        success_rate = entry.get("success_rate")
        if success_rate is None:
            return None

        severity = "stable"
        reason = ""
        if success_rate < SUCCESS_RATE_CRITICAL:
            severity = "critical"
            reason = f"成功率 {success_rate:.1%} 低于安全阈值 {SUCCESS_RATE_CRITICAL:.1%}"
        elif success_rate < SUCCESS_RATE_WARNING:
            severity = "warning"
            reason = f"成功率 {success_rate:.1%} 低于建议阈值 {SUCCESS_RATE_WARNING:.1%}"

        if severity != "stable":
            return DriftRecord(
                skill_id=skill_id,
                drift_type="success_rate",
                drift_direction="down",
                drift_score=round(1 - success_rate, 4),
                previous_value=None,   # 单次分析无历史对比，用 current_value
                current_value=success_rate,
                severity=severity,
                detected_at=datetime.now().isoformat(),
                reason=reason,
            )
        return None

    def _check_risk_drift(self, skill_id: str, entry: dict[str, Any]) -> DriftRecord | None:
        """
        检查风险等级是否比初始时升高。
        初始 risk_level 记录在 skill_index entry 的 risk_level 字段。
        """
        current_risk = entry.get("risk_level", "low")
        # 风险等级映射
        risk_order = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
        current_score = risk_order.get(current_risk, 0)
        # 尝试从历史记录中找初始风险等级
        # 目前 skill_index 中只有当前值，这里用 initial_risk_level 字段（如果有的话）
        initial_risk = entry.get("initial_risk_level", current_risk)
        initial_score = risk_order.get(initial_risk, 0)
        if current_score > initial_score:
            drift_score = (current_score - initial_score) / 4.0
            severity = "drift" if drift_score < 0.75 else "critical"
            return DriftRecord(
                skill_id=skill_id,
                drift_type="risk_level",
                drift_direction="up",
                drift_score=round(drift_score, 4),
                previous_value=initial_risk,
                current_value=current_risk,
                severity=severity,
                detected_at=datetime.now().isoformat(),
                reason=f"风险等级从 {initial_risk} 升至 {current_risk}",
            )
        return None

    def _check_staleness(self, skill_id: str, entry: dict[str, Any]) -> DriftRecord | None:
        """
        检查技能是否长期未使用。
        """
        last_used = entry.get("last_used")
        if not last_used:
            # 从未使用过
            usage_count = entry.get("usage_count", 0)
            if usage_count == 0:
                # 从未使用超过 STALENESS_DAYS（以 created_at 为基准）
                created_at = entry.get("created_at", "")
                if created_at:
                    try:
                        created = datetime.fromisoformat(created_at)
                        days_since = (datetime.now() - created).days
                        if days_since > STALENESS_DAYS:
                            return DriftRecord(
                                skill_id=skill_id,
                                drift_type="usage",
                                drift_direction="down",
                                drift_score=min(days_since / (STALENESS_DAYS * 3), 1.0),
                                previous_value=None,
                                current_value=f"从未使用（已创建 {days_since} 天）",
                                severity="warning",
                                detected_at=datetime.now().isoformat(),
                                reason=f"技能已创建 {days_since} 天但从未被使用",
                            )
                    except ValueError:
                        pass
            return None

        try:
            last_dt = datetime.fromisoformat(last_used)
            days_ago = (datetime.now() - last_dt).days
            if days_ago > STALENESS_DAYS:
                severity = "warning" if days_ago < STALENESS_DAYS * 2 else "drift"
                return DriftRecord(
                    skill_id=skill_id,
                    drift_type="usage",
                    drift_direction="down",
                    drift_score=min(days_ago / (STALENESS_DAYS * 3), 1.0),
                    previous_value=last_used,
                    current_value=f"最近 {days_ago} 天未使用",
                    severity=severity,
                    detected_at=datetime.now().isoformat(),
                    reason=f"技能已 {days_ago} 天未被调用（阈值 {STALENESS_DAYS} 天）",
                )
        except ValueError:
            pass
        return None

    def _check_rapid_failure(self, skill_id: str, entry: dict[str, Any]) -> DriftRecord | None:
        """
        检查是否有连续失败模式。
        逻辑：最近 N 次使用全是失败。
        这里用 success_count / usage_count 推算，
        更精确的实现需要使用历史使用记录（见 Curator 历史日志）。
        """
        usage_count = entry.get("usage_count", 0)
        success_count = entry.get("success_count", 0)
        if usage_count < 3:
            return None
        fail_count = usage_count - success_count
        # 如果失败率 > 66%，且使用次数 >= 3
        if usage_count >= 3 and success_count == 0:
            return DriftRecord(
                skill_id=skill_id,
                drift_type="success_rate",
                drift_direction="down",
                drift_score=1.0,
                previous_value=None,
                current_value=0.0,
                severity="critical",
                detected_at=datetime.now().isoformat(),
                reason=f"最近 {usage_count} 次使用全部失败，成功率 0%",
            )
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _overall_severity(self, records: list[DriftRecord]) -> str:
        """取最严重的级别。"""
        if any(r.severity == "critical" for r in records):
            return "critical"
        if any(r.severity == "drift" for r in records):
            return "drift"
        if any(r.severity == "warning" for r in records):
            return "warning"
        return "stable"

    def _make_recommendations(
        self,
        records: list[DriftRecord],
        severity: str,
        entry: dict[str, Any],
    ) -> list[str]:
        """根据漂移记录生成处理建议。"""
        recs: list[str] = []
        for r in records:
            if r.drift_type == "success_rate" and r.drift_direction == "down":
                if severity == "critical":
                    recs.append("建议立即归档（success_rate 严重低于安全阈值）")
                else:
                    recs.append("建议人工复核成功率，必要时降级或归档")
            elif r.drift_type == "risk_level" and r.drift_direction == "up":
                recs.append("建议人工复核技能风险等级变化原因，更新风险策略")
            elif r.drift_type == "usage":
                if severity == "drift":
                    recs.append("建议归档（长期未使用的陈旧技能）")
                else:
                    recs.append("建议标记为 stale，增加监控频率")
            elif r.drift_type == "success_rate" and entry.get("success_count", 1) == 0:
                recs.append("建议立即归档（连续失败，疑似失效）")
        return recs
