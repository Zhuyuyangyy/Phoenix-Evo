"""
TaskTypeClassifier — Phoenix-Evo V1.0 P0-1
==========================================

轻量、规则优先的任务类型分类器。
不调用 LLM，不引入重依赖，基于关键词+模式匹配输出 task_type。

目录约束：
  放在 Phoenix-Evo/runtime/，从 run_agent.py 通过 PHOENIX_EVO_DIR 导入。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


# ── 规则定义 ─────────────────────────────────────────────────────────────────

_TASK_TYPE_PATTERNS: list[dict] = [
    {
        "task_type": "code_repair",
        "keywords": [
            # 错误类型
            r"\bSyntaxError\b", r"\bTypeError\b", r"\bImportError\b",
            r"\bAttributeError\b", r"\bValueError\b", r"\bIndexError\b",
            r"\bKeyError\b", r"\bRuntimeError\b", r"\bZeroDivisionError\b",
            r"\bNameError\b", r"\bIndentationError\b", r"\bOSError\b",
            # 修复信号
            r"修复\b", r"修 bug\b", r"修好\b", r"报错\b", r"出错\b",
            r"失败\b.*修复", r"fix\b", r"repair\b", r"debug\b",
            # 文件损坏
            r"文件损坏\b", r"null 字节", r"文件.*坏",
            # 通用代码问题
            r"代码.*问题", r"程序.*崩溃", r"crash\b",
        ],
        "weight": 1.0,
    },
    {
        "task_type": "test_debugging",
        "keywords": [
            r"\bpytest\b", r"\bunittest\b", r"\btest fail\b",
            r"测试.*不通过", r"测试.*失败", r"demo.*fail",
            r"回归测试\b", r"test.*error\b", r"测试.*报错",
            r"\b AssertionError\b", r"all.*test.*fail",
            r"跑.*测试", r"测试.*跑了", r"test suite",
            r"demo.*fail", r"demo.*报错", r"demo.*不通过",
        ],
        "weight": 1.0,
    },
    {
        "task_type": "documentation",
        "keywords": [
            # 文档类型
            r"写.*文档", r"写.*说明", r"写.*报告",
            r"\bREADME\b", r"技术.*文档", r"设计.*文档",
            # 专利
            r"专利交底书", r"专利.*撰写", r"专利.*写作",
            # 论文
            r"论文\b", r"SCI\b", r"期刊.*文章", r"学术.*写作",
            # 项目书/商业计划
            r"商业计划书", r"项目.*书", r"申报材料",
            # PPT/演讲
            r"PPT\b", r"路演", r"演讲稿", r"汇报材料",
        ],
        "weight": 0.95,
    },
    {
        "task_type": "architecture_planning",
        "keywords": [
            # 架构设计
            r"架构\b", r"系统设计\b", r"模块拆分\b",
            r"技术选型\b", r"设计.*架构",
            # 规划
            r"V\d+\.\d+.*规划", r"V1\.0\b.*规划",
            r"路线图\b", r"roadmap\b", r"路线.*规划",
            r"下一阶段", r"迭代计划",
            # 方案
            r"实现方案\b", r"技术方案\b", r"解决方案\b",
            # 重构
            r"重构\b", r"refactor\b",
        ],
        "weight": 0.95,
    },
    {
        "task_type": "frontend_ui",
        "keywords": [
            r"\bVue\b", r"\bReact\b", r"\bAngular\b",
            r"\bCSS\b", r"\bHTML\b", r"\bTailwind\b",
            r"前端\b", r"UI\b.*优化", r"界面.*美化",
            r"组件\b.*编写", r"组件.*开发",
            r"页面.*优化", r"页面.*美化",
            r"暗色主题", r"dark mode",
            r"样式.*调整", r"layout\b",
            r"\bFigma\b",
        ],
        "weight": 1.0,
    },
    {
        "task_type": "data_experiment",
        "keywords": [
            # 实验
            r"\b ablation\b", r"消融实验", r"ablation.*study",
            r"\bbenchmark\b", r"基准测试\b",
            r"跑.*实验", r"实验.*结果",
            # 指标
            r"指标\b", r"mIoU\b", r"accuracy\b", r"precision\b",
            r"recall\b", r"F1\b", r"loss\b",
            # 数据
            r"生成.*csv", r"数据.*可视化",
            r"训练.*指标", r"评测.*结果",
            # 图表
            r"绘制.*曲线", r"生成.*图表", r"plot\b",
        ],
        "weight": 0.95,
    },
    {
        "task_type": "project_management",
        "keywords": [
            r"任务.*分配", r"团队.*协作", r"进度.*跟踪",
            r"Scrum\b", r"看板\b", r"Kanban\b",
            r"里程碑\b", r"deadline\b",
            r"代码审查", r"code review",
            r"PR\b.*合并", r"merge\b",
        ],
        "weight": 0.9,
    },
]


# ── 数据类 ───────────────────────────────────────────────────────────────────

@dataclass
class ClassificationResult:
    task_type: str
    confidence: float
    matched_rules: list[str]
    fallback: bool

    def __repr__(self) -> str:
        return (
            f"ClassificationResult(task_type={self.task_type!r}, "
            f"confidence={self.confidence:.2f}, "
            f"matched={self.matched_rules!r}, "
            f"fallback={self.fallback})"
        )


# ── 分类器 ───────────────────────────────────────────────────────────────────

class TaskTypeClassifier:
    """
    轻量任务类型分类器。

    使用方法：
        classifier = TaskTypeClassifier()
        result = classifier.classify("修复这个 SyntaxError 文件")
        # result.task_type → "code_repair"
        # result.confidence → 0.85
        # result.matched_rules → ["SyntaxError", "修复"]
    """

    def __init__(self, default_type: str = "general"):
        self.default_type = default_type
        # 预编译所有正则，提升速度
        self._compiled: list[tuple[str, re.Pattern, float]] = []
        for entry in _TASK_TYPE_PATTERNS:
            tt = entry["task_type"]
            weight = entry.get("weight", 1.0)
            for kw in entry["keywords"]:
                try:
                    pattern = re.compile(kw, re.IGNORECASE)
                    self._compiled.append((tt, pattern, weight))
                except re.error:
                    # Skip invalid regex
                    pass

    def classify(self, message: str) -> ClassificationResult:
        """
        对输入消息进行任务类型分类。

        Args:
            message: 用户消息或任务描述

        Returns:
            ClassificationResult，包含 task_type, confidence, matched_rules, fallback
        """
        if not message or not isinstance(message, str):
            return ClassificationResult(
                task_type=self.default_type,
                confidence=0.0,
                matched_rules=[],
                fallback=True,
            )

        message_lower = message.lower()

        # Score each task type by counting keyword matches
        scores: dict[str, float] = {}
        rule_matches: dict[str, list[str]] = {}

        for tt, pattern, weight in self._compiled:
            matches = pattern.findall(message)
            if matches:
                # Count unique matches (deduplicate)
                unique_matches = list(dict.fromkeys(matches))
                score = len(unique_matches) * weight
                scores[tt] = scores.get(tt, 0) + score
                rule_matches[tt] = rule_matches.get(tt, []) + [
                    m if len(m) <= 40 else m[:37] + "..."
                    for m in unique_matches
                ]

        if not scores:
            return ClassificationResult(
                task_type=self.default_type,
                confidence=0.3,
                matched_rules=[],
                fallback=True,
            )

        # Pick highest scoring type
        best_type = max(scores, key=lambda k: scores[k])
        raw_score = scores[best_type]

        # Normalize confidence: higher raw score → higher confidence
        # Cap at 0.95 to avoid false certainty with few matches
        max_possible = sum(
            len(entry["keywords"]) * entry.get("weight", 1.0)
            for entry in _TASK_TYPE_PATTERNS
            if entry["task_type"] == best_type
        )
        confidence = min(raw_score / max(max_possible, 1), 0.95)
        confidence = max(confidence, 0.4)  # Minimum meaningful confidence

        return ClassificationResult(
            task_type=best_type,
            confidence=round(confidence, 2),
            matched_rules=rule_matches.get(best_type, []),
            fallback=False,
        )


# ── 单例（全局复用，避免重复编译正则）────────────────────────────────────────

_classifier_instance: Optional[TaskTypeClassifier] = None


def get_classifier() -> TaskTypeClassifier:
    """Return a shared classifier instance."""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = TaskTypeClassifier()
    return _classifier_instance


def classify_task(message: str) -> ClassificationResult:
    """
    Convenience function — classify in one call.

    Usage:
        result = classify_task("修复这个 pytest demo fail 了")
        assert result.task_type == "test_debugging"
    """
    return get_classifier().classify(message)
