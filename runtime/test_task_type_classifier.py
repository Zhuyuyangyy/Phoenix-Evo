#!/usr/bin/env python3
"""
P0-2 验证脚本：6 类 task_type 分类测试
Run from Phoenix-Evo root:
    python runtime/test_task_type_classifier.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from task_type_classifier import TaskTypeClassifier

TEST_CASES = [
    # (input, expected_type, description)
    ("修复这个 SyntaxError 文件", "code_repair", "SyntaxError + 修复"),
    ("这个 pytest demo fail 了", "test_debugging", "pytest + demo fail"),
    ("写一份 V1.0 技术说明文档", "documentation", "技术文档 + V1.0"),
    ("规划 Phoenix-Evo V1.0 架构", "architecture_planning", "架构 + 规划 + V1.0"),
    ("优化 Vue 前端页面 UI", "frontend_ui", "Vue + UI"),
    ("跑 ablation 实验并生成指标表", "data_experiment", "ablation + 指标"),
    # 兜底
    ("打开一个文件", "general", "无特征 → general"),
    # 混合：两个类型打架
    ("修复 pytest 测试失败并规划 V2.0 架构", None, "多类型 → 高分胜出"),
]

def run():
    classifier = TaskTypeClassifier()
    passed = 0
    failed = 0

    for msg, expected, desc in TEST_CASES:
        result = classifier.classify(msg)
        ok = (
            expected is None  # ambiguous case — just show
            or result.task_type == expected
        )
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1

        print(f"[{status}] {desc}")
        print(f"       input:    {msg!r}")
        print(f"       got:      task_type={result.task_type!r}  confidence={result.confidence}")
        print(f"       expected: {expected!r}")
        print(f"       rules:    {result.matched_rules}")
        print()

    total = passed + failed
    print(f"{'='*50}")
    print(f"Results: {passed}/{total} passed")
    if failed:
        print(f"FAILURES: {failed}")
        sys.exit(1)
    else:
        print("ALL PASS")
        sys.exit(0)

if __name__ == "__main__":
    run()
