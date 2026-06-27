"""
RiskPolicy: 风险策略定义
V0.2 — Phoenix-Evo Immune Guard

定义免疫规则的元数据：危险行为关键词、高风险标签、quarantine 阈值等。
所有规则均为静态配置，不涉及运行时推理。
"""

from dataclasses import dataclass, field
from typing import Literal

# ── 危险行为分类 ────────────────────────────────────────────

DANGEROUS_PATTERNS: list[tuple[str, str, list[str]]] = [
    # (category, description, keyword_list)
    ("privilege_escalation", "权限提升/绕过", [
        "绕过", "权限检查", "sudo", "root", "admin", "privilege", "escalate",
        "bypass", "unauthorized", "无权限", "提权",
    ]),
    ("data_theft", "数据窃取", [
        "cat /etc/passwd", "/etc/shadow", "爬取", "窃取", "dump",
        "password", "密码", "credential", "api_key", "token",
        "隐私数据", "个人信息", "身份证", "银行卡",
    ]),
    ("destruction", "破坏性操作", [
        "rm -rf", "drop table", "delete *", "format", "truncate",
        "删除所有", "清空", "destroy", "毁灭",
    ]),
    ("network_attack", "网络攻击", [
        "sql注入", "xss", "csrf", "ddos", "ping flood",
        "injection", "exploit", "payload", "shell",
    ]),
    ("privacy_violation", "隐私侵犯", [
        "监控", "追踪", "gps定位", "监听", "窃听",
        "未经同意", "隐私", "personal data",
    ]),
    ("payment_fraud", "支付欺诈", [
        "支付", "转账", "银行卡", "信用卡", "payment",
        "billing", "charge", "refund fraud",
    ]),
    ("persistence", "持久化后门", [
        "后门", "backdoor", "reverse shell", "nc -e",
        "crontab", "自启动", "autorun", "bootkit",
    ]),
    ("ai_harm", "AI 危害行为", [
        "prompt injection", "prompt leak", "jailbreak", "越狱",
        "role play 绕过", "system prompt 提取", "指令注入",
    ]),
]

HIGH_RISK_TAGS = {
    "privilege_escalation",
    "destruction",
    "payment_fraud",
    "persistence",
    "ai_harm",
}

MEDIUM_RISK_TAGS = {
    "data_theft",
    "network_attack",
    "privacy_violation",
}

# ── 免疫决策常量 ────────────────────────────────────────────

IMMUNE_DECISION = Literal["draft", "quarantine", "reject"]

# 来源轨迹质量
SOURCE_FAILED_WEIGHT = 0.7       # 来自失败轨迹 → quarantine 权重
SOURCE_SUCCESS_WEIGHT = 0.0      # 来自成功轨迹 → 无额外惩罚
SOURCE_UNKNOWN_WEIGHT = 0.3      # 来自外部轨迹 → 轻微 quarantine 倾向

# 证据充分性（必须同时满足）
EVIDENCE_REQUIRED = ["trajectory_id", "task_success"]
EVIDENCE_RECOMMENDED = ["artifacts", "validation_steps"]

# 泛化程度阈值
MIN_PROCEDURE_STEPS = 2          # 至少 2 步才不算"过度泛化"
MAX_GOAL_LENGTH = 10             # goal 超过 N 个词 → 警惕过度特化（其实要反过来）

# 反复失败阈值（同一 skill 失败 N 次 → immune_memory 记录）
REPEAT_FAILURE_THRESHOLD = 3

# ── 风险评分计算 ────────────────────────────────────────────

@dataclass
class RiskProfile:
    """单一技能候选的风险画像。"""
    risk_level: Literal["low", "medium", "high", "critical"] = "low"
    tags: list[str] = field(default_factory=list)
    dangerous_patterns_found: list[str] = field(default_factory=list)
    source_failed: bool = False
    has_trajectory_id: bool = False
    has_artifacts: bool = False
    has_verification: bool = False
    procedure_step_count: int = 0
    goal_length: int = 0
    similar_skill_failures: int = 0  # immune_memory 中记录次数
    warnings: list[str] = field(default_factory=list)
    immune_decision: IMMUNE_DECISION = "draft"

    @property
    def has_high_risk_tag(self) -> bool:
        return bool(set(self.tags) & HIGH_RISK_TAGS)

    @property
    def has_medium_risk_tag(self) -> bool:
        return bool(set(self.tags) & MEDIUM_RISK_TAGS)

    @property
    def evidence_complete(self) -> bool:
        # 核心证据要求：轨迹ID + 产物记录 + 真实步骤
        return self.has_trajectory_id and self.has_artifacts and self.procedure_step_count >= 3

    @property
    def overgeneralized(self) -> bool:
        # 单次经验写成通用规则
        return self.procedure_step_count < MIN_PROCEDURE_STEPS

    def compute_decision(self) -> "RiskProfile":
        """根据规则计算免疫决策。优先级：reject > quarantine > draft。"""
        decision = "draft"

        # 1. 高风险标签 → 直接 reject
        if self.has_high_risk_tag:
            decision = "reject"
            self.warnings.append(f"高危标签: {set(self.tags) & HIGH_RISK_TAGS}")

        # 2. 危险模式命中 → reject
        elif self.dangerous_patterns_found:
            decision = "reject"
            self.warnings.append(f"危险模式: {self.dangerous_patterns_found}")

        # 3. 过度泛化 → quarantine
        elif self.overgeneralized:
            decision = "quarantine"
            self.warnings.append(f"过度泛化（仅{self.procedure_step_count}步）")

        # 4. 来自失败轨迹 + 证据不全 → quarantine
        elif self.source_failed and not self.has_artifacts:
            decision = "quarantine"
            self.warnings.append("失败轨迹 + 无产物记录")

        # 5. 来自失败轨迹 + 无验证步骤 → quarantine
        elif self.source_failed and not self.has_verification:
            decision = "quarantine"
            self.warnings.append("失败轨迹 + 无验证步骤")

        # 6. 证据不全（无论来源）→ quarantine
        elif not self.evidence_complete:
            decision = "quarantine"
            self.warnings.append(f"证据不全: 需要 {[e for e in EVIDENCE_REQUIRED if not getattr(self, e, False)]}")

        # 7. 反复失败记录 → quarantine
        elif self.similar_skill_failures >= REPEAT_FAILURE_THRESHOLD:
            decision = "quarantine"
            self.warnings.append(f"同类技能历史失败{self.similar_skill_failures}次")

        # 8. 中等风险标签 → quarantine
        elif self.has_medium_risk_tag:
            decision = "quarantine"
            self.warnings.append(f"中等风险标签: {set(self.tags) & MEDIUM_RISK_TAGS}")

        # 9. 缺少推荐证据 → 加警告但不阻塞
        elif not self.has_artifacts:
            self.warnings.append("缺少 artifacts 证据")

        self.immune_decision = decision
        return self


# ── RiskPolicy 包装类（供 ImmuneGuard 使用）─────────────────────

class RiskPolicy:
    """
    封装 risk_policy.py 中的规则，提供 evaluate() 和 compute_decision()。
    """

    def evaluate(self, profile: RiskProfile) -> RiskProfile:
        if profile.has_high_risk_tag:
            profile.risk_level = 'critical'
        elif profile.dangerous_patterns_found:
            profile.risk_level = 'high'
        elif profile.has_medium_risk_tag:
            profile.risk_level = 'medium'
        else:
            profile.risk_level = 'low'
        return profile

    def compute_decision(self, profile: RiskProfile) -> RiskProfile:
        return profile.compute_decision()
