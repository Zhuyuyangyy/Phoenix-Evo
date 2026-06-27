"""
ProjectRouter — Phoenix-Evo V1.0 P0-3
======================================

从 user_message 中识别当前任务所属的项目 namespace。
用于按项目过滤 Phoenix 技能库检索结果。

项目列表取自 D:/ZYY Project/ 目录（Hermes 主工作区），
按真实项目子目录名称维护。
"""

from __future__ import annotations

import re

# ── 已知项目 namespace ───────────────────────────────────────────────────────

# 格式：(namespace_id, 显示名, 匹配模式)
# namespace_id = SkillRetriever / skill_index 中的 project 值
# matched_against = 消息中出现的文本 → 映射到该项目
_PROJECT_RULES: list[tuple[str, str, list[str | re.Pattern]]] = [
    (
        "TCM-Mind-RAG",
        "岐黄问道-中医知识问答系统",
        [
            "TCM-Mind-RAG",
            "岐黄问道",
            "中医知识问答",
            "中医 RAG",
            "TCM RAG",
            "神经符号",
        ],
    ),
    (
        "AgentShield",
        "AgentShield 安全防护系统",
        [
            "AgentShield",
            "agent-shield",
            "安全防护",
            "Agent Shield",
        ],
    ),
    (
        "OrthoSim-3D",
        "OrthoSim-3D 骨科仿真系统",
        [
            "OrthoSim-3D",
            "OrthoSim",
            "骨科仿真",
        ],
    ),
    (
        "AutoDataFlow",
        "AutoDataFlow 数据流自动化",
        [
            "AutoDataFlow",
            "DataFlow",
            "数据流",
        ],
    ),
    (
        "LiteSegNet",
        "LiteSegNet 轻量级分割网络",
        [
            "LiteSegNet",
            "IFS-SegNet",
            "分割网络",
            "图像分割",
        ],
    ),
    (
        "Phoenix-Evo",
        "Phoenix-Evo 自进化系统",
        [
            "Phoenix-Evo",
            "Phoenix Evo",
            "phoenix-evo",
            "phoenix_evo",
            "自进化",
        ],
    ),
    (
        "Hermes-Agent",
        "Hermes Agent 主系统",
        [
            "Hermes Agent",
            "hermes-agent",
            "run_agent.py",
        ],
    ),
    (
        "MedPaper",
        "MedPaper 医学论文生成",
        [
            "MedPaper",
            "医学论文",
        ],
    ),
    (
        "CSPaper",
        "CSPaper 计算机论文生成",
        [
            "CSPaper",
        ],
    ),
    (
        "marketing-council",
        "MarketingCouncil 营销委员会",
        [
            "marketing-council",
            "MarketingCouncil",
        ],
    ),
    (
        "generic-sys-admin",
        "通用系统管理后端",
        [
            "generic-sys-admin",
            "sys-admin",
        ],
    ),
    (
        "ReflexMarket-AI",
        "ReflexMarket-AI 反射市场智能",
        [
            "ReflexMarket",
            "ReflexMarket-AI",
        ],
    ),
]


# ── 数据类 ───────────────────────────────────────────────────────────────────

class ProjectMatch:
    namespace: str
    display_name: str
    confidence: float  # 0.0~1.0

    def __init__(self, namespace: str, display_name: str, confidence: float):
        self.namespace = namespace
        self.display_name = display_name
        self.confidence = confidence

    def __repr__(self) -> str:
        return (
            f"ProjectMatch(namespace={self.namespace!r}, "
            f"display={self.display_name!r}, conf={self.confidence:.2f})"
        )


# ── ProjectRouter ─────────────────────────────────────────────────────────────

class ProjectRouter:
    """
    从用户消息中识别项目 namespace。

    使用方法：
        router = ProjectRouter()
        match = router.classify_project("在 TCM-Mind-RAG 里修个 bug")
        if match:
            print(match.namespace)   # "TCM-Mind-RAG"
            print(match.confidence)  # 0.95
    """

    def __init__(self):
        # 预编译，提升速度
        self._rules: list[tuple[str, str, re.Pattern]] = []
        for namespace, display, patterns in _PROJECT_RULES:
            for p in patterns:
                if isinstance(p, str):
                    # 转义特殊字符，按单词边界匹配
                    escaped = re.escape(p)
                    pattern = re.compile(r'\b' + escaped + r'\b', re.IGNORECASE)
                else:
                    pattern = p
                self._rules.append((namespace, display, pattern))

    def classify_project(self, message: str) -> ProjectMatch | None:
        """
        从消息中识别项目 namespace。

        Args:
            message: 用户消息或任务描述

        Returns:
            ProjectMatch 或 None（未识别到任何已知项目）
        """
        if not message or not isinstance(message, str):
            return None

        scores: dict[str, tuple[str, int]] = {}  # namespace → (display_name, hit_count)

        for namespace, display, pattern in self._rules:
            if pattern.search(message):
                scores[namespace] = (display, scores.get(namespace, (display, 0))[1] + 1)

        if not scores:
            return None

        # 取命中次数最多的项目
        best_ns = max(scores, key=lambda k: scores[k][1])
        display, hits = scores[best_ns]

        # confidence = hits / max_possible_hits（归一化到 0.6~0.95）
        max_hits = max(hits for _, (_, h) in scores.items())
        confidence = min(0.6 + (hits / max(max_hits, 1)) * 0.35, 0.95)
        confidence = round(confidence, 2)

        return ProjectMatch(namespace=best_ns, display_name=display, confidence=confidence)

    def get_all_projects(self) -> list[str]:
        """返回所有已知项目 namespace 列表。"""
        seen: set[str] = set()
        result: list[str] = []
        for ns, _, _ in _PROJECT_RULES:
            if ns not in seen:
                seen.add(ns)
                result.append(ns)
        return result


# ── 单例 ─────────────────────────────────────────────────────────────────────

_router_instance: ProjectRouter | None = None


def get_project_router() -> ProjectRouter:
    global _router_instance
    if _router_instance is None:
        _router_instance = ProjectRouter()
    return _router_instance


def classify_project(message: str) -> ProjectMatch | None:
    """便捷函数。"""
    return get_project_router().classify_project(message)
