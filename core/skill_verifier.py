"""
SkillVerifier: 技能验证器
V0.1 — Phoenix-Evo

职责：验证候选技能是否安全、可信、可复用。
      V0.1：纯规则检查，不调用 LLM。
      验证通过 → 进入 skills/draft/
      验证拒绝 → 记录拒绝原因，不写入
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ── 危险关键词列表 ───────────────────────────────────────────

DANGEROUS_PATTERNS = [
    # 破坏性操作
    (re.compile(r'\brm\s+-rf\b', re.I),     "禁止删除操作: rm -rf"),
    (re.compile(r'\bsudo\s+rm\b', re.I),   "禁止 sudo 删除"),
    (re.compile(r'\bdrop\s+table\b', re.I),"禁止删库"),
    (re.compile(r'\bdelete\s+all\b', re.I),"禁止全量删除"),
    (re.compile(r'\btruncate\b', re.I),     "禁止清空表/文件"),
    (re.compile(r'\bshred\b', re.I),        "禁止销毁文件"),
    # 支付/金融
    (re.compile(r'\bpayment\b', re.I),      "支付相关操作"),
    (re.compile(r'\btransfer\b.*money', re.I), "转账操作"),
    (re.compile(r'\bsql\s*inject', re.I),   "SQL 注入"),
    # 隐私/安全
    (re.compile(r'\bsudo\s+chmod\s+0\b', re.I), "权限降级"),
    (re.compile(r'\beval\s*\(', re.I),     "动态代码执行 eval"),
    (re.compile(r'\bexec\s*\(', re.I),      "动态代码执行 exec"),
    (re.compile(r'\bpickle\.loads?\b', re.I),"pickle 反序列化"),
    (re.compile(r'\bsubprocess.*shell\s*=\s*True', re.I), "shell=True 风险"),
    # 欺骗/绕过
    (re.compile(r'\bfake\b', re.I),         "伪造内容"),
    (re.compile(r'\bimpersonat', re.I),     "冒充行为"),
    (re.compile(r'\bbypass\b', re.I),        "绕过检查"),
    (re.compile(r'\bbackdoor\b', re.I),     "后门相关"),
    # 过度泛化
    (re.compile(r'\balways\b', re.I),       "过度绝对表述"),
    (re.compile(r'\bnever\s+fail\b', re.I), "不可能失败声明"),
    (re.compile(r'\bguarantee\b', re.I),    "保证类表述"),
]

# 高风险任务类型
HIGH_RISK_TYPES = {"payment", "auth_bypass", "penetration", "data_destruction", "privacy_steal"}


@dataclass
class VerificationResult:
    passed: bool
    confidence: float          # 0.0–1.0
    risk_level: str            # low / medium / high / rejected
    activation_level: str      # draft / reject
    reason: str               # 验证理由
    warnings: list[str]        # 警告列表（非拒绝原因）
    checked_items: dict[str, bool]  # 每项检查的结果


class SkillVerifier:
    """
    验证候选技能的安全性和可信度。

    使用方式：
        result = SkillVerifier.verify(skill_candidate, trajectory)
        if result.passed:
            registry.add_draft(skill_candidate)
        else:
            print(f"拒绝: {result.reason}")
    """

    def __init__(self):
        self._dangerous = DANGEROUS_PATTERNS

    def verify(self, skill: dict[str, Any], trajectory: dict[str, Any]) -> VerificationResult:
        """
        主验证入口。
        """
        checks = {}

        # ── Check 1: 来源可信 ──────────────────────────────
        checks["has_trajectory"] = bool(trajectory.get("task_id"))
        checks["has_goal"] = bool(trajectory.get("task_goal"))

        # ── Check 2: 任务类型风险 ──────────────────────────
        risk_level, risk_reason = self._check_risk_level(trajectory)
        checks["task_type_safe"] = (risk_level != "high")

        # ── Check 3: 危险内容扫描 ─────────────────────────
        danger_results = self._scan_dangerous_content(skill.get("skill_md", ""))
        checks["no_dangerous_content"] = danger_results["clean"]
        danger_warnings = danger_results["matches"]

        # ── Check 4: 过度泛化检测 ─────────────────────────
        overgen = self._check_overgeneralization(skill.get("skill_md", ""))
        checks["not_overgeneralized"] = overgen["clean"]
        overgen_warnings = overgen["warnings"]

        # ── Check 5: 轨迹支撑数量 ─────────────────────────
        # V0.1: 只检查当前轨迹，暂不查历史
        checks["has_artifacts"] = bool(trajectory.get("artifacts") or trajectory.get("final_output"))
        checks["has_verification"] = bool(trajectory.get("actions") and any(
            "verify" in a.get("action", "").lower() or "check" in a.get("action", "").lower()
            for a in trajectory.get("actions", [])
        ))

        # ── Check 6: 与已有技能重复 ────────────────────────
        duplicate = self._check_duplicate(skill.get("skill_name", ""))
        checks["not_duplicate"] = not duplicate
        duplicate_warning = duplicate

        # ── 综合判定 ───────────────────────────────────────
        all_passed = all([
            checks["has_trajectory"],
            checks["has_goal"],
            checks["task_type_safe"],
            checks["no_dangerous_content"],
            checks["not_overgeneralized"],
            checks["not_duplicate"],
        ])

        warnings = []
        if danger_warnings:
            warnings.extend([f"危险内容: {w}" for w in danger_warnings])
        if overgen_warnings:
            warnings.extend(overgen_warnings)
        if duplicate_warning:
            warnings.append(f"可能与现有技能重复: {duplicate_warning}")

        # 置信度：通过的检查项越多越高
        n_checks = len(checks)
        n_passed = sum(checks.values())
        confidence = n_passed / n_checks if n_checks else 0.0

        if not all_passed:
            return VerificationResult(
                passed=False,
                confidence=confidence,
                risk_level="rejected",
                activation_level="reject",
                reason=f"技能验证未通过。失败项: {[k for k,v in checks.items() if not v]}",
                warnings=warnings,
                checked_items=checks,
            )

        # 通过：有警告 → medium；无警告 → low
        final_risk = "medium" if warnings else "low"
        reason = (
            f"技能验证通过（置信度 {confidence:.0%}，风险等级 {final_risk}）。"
            f"{'存在警告: ' + ', '.join(warnings) if warnings else '无警告。'}"
        )

        return VerificationResult(
            passed=True,
            confidence=confidence,
            risk_level=final_risk,
            activation_level="draft",   # V0.1: 只到 draft，不自动激活
            reason=reason,
            warnings=warnings,
            checked_items=checks,
        )

    # ── 子检查 ────────────────────────────────────────────

    def _check_risk_level(self, traj: dict) -> tuple[str, str]:
        task_type = traj.get("task_type", "").lower()
        risk = traj.get("risk_level", "low").lower()
        if task_type in HIGH_RISK_TYPES or risk == "high":
            return "high", f"任务类型={task_type} 或风险等级={risk}"
        if risk == "medium" or task_type in {"coding", "write", "debugging"}:
            return "medium", f"任务类型={task_type}"
        return "low", "低风险任务"

    def _scan_dangerous_content(self, md: str) -> dict:
        matches = []
        for pattern, description in self._dangerous:
            if pattern.search(md):
                matches.append(description)
        return {"clean": len(matches) == 0, "matches": matches}

    def _check_overgeneralization(self, md: str) -> dict:
        warnings = []
        lines = md.split("\n")
        vague_count = 0
        for line in lines:
            lower = line.lower()
            if any(kw in lower for kw in ["一切", "所有", "全部", "always", "never", "guarantee", "无论", "无论何种"]):
                vague_count += 1
                warnings.append(f"过度泛化表述: {line.strip()[:60]}")

        # 检查是否有具体步骤（至少3步）
        # Count procedure steps: "1. xxx" or "- 1. xxx" or "  1. xxx"
        import re as _re
        procedure_count = 0
        for l in lines:
            stripped = l.strip()
            # Match "- N. " or just "N. " at line start
            if _re.match(r"^-?\s*\d+\.\s+", stripped):
                procedure_count += 1
        if procedure_count < 2:
            warnings.append(f"技能步骤不足（仅{procedure_count}步），可能过于笼统")

        return {"clean": vague_count == 0 and procedure_count >= 2, "warnings": warnings}

    def _check_duplicate(self, skill_name: str) -> str:
        """检查是否与已有技能同名。"""
        skills_dir = Path(__file__).parent.parent / "skills"
        for folder in ["draft", "active"]:
            folder_path = skills_dir / folder
            if not folder_path.exists():
                continue
            for f in folder_path.glob("*.md"):
                fname = f.stem.lower()
                if skill_name.lower() in fname or fname in skill_name.lower():
                    return f"与 {f.name} 潜在重复"
        return ""
