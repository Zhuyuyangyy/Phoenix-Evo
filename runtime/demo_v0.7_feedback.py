#!/usr/bin/env python3
"""Phoenix-Evo V0.7 Feedback Dispatcher Test"""

import sys
import traceback
from pathlib import Path

PHOENIX_BASE = Path(__file__).parent.parent
sys.path.insert(0, str(PHOENIX_BASE))

from runtime.feedback_dispatcher import FeedbackDispatcher, Threshold
from runtime.outcome_tracker import OutcomeTracker


def test_report_success():
    print()
    print("=" * 60)
    print("  Test 1: FeedbackDispatcher.report_success")
    print("=" * 60)
    dispatcher = FeedbackDispatcher(phoenix_base_dir=PHOENIX_BASE, reporter_base_dir=PHOENIX_BASE, mode="sync")
    result = dispatcher.report_success(skill_id="test_success_skill", task_id="t_success_001", session_id="s_test_001", duration=1.23)
    print(f"  result: {result}")
    assert result.get("skill_id") == "test_success_skill"
    assert result.get("success") is True
    print("  PASS")
    return True


def test_report_failure():
    print()
    print("=" * 60)
    print("  Test 2: FeedbackDispatcher.report_failure")
    print("=" * 60)
    dispatcher = FeedbackDispatcher(phoenix_base_dir=PHOENIX_BASE, reporter_base_dir=PHOENIX_BASE, mode="sync")
    result1 = dispatcher.report_failure(skill_id="test_fail_skill", failure_reason="assertion_error", risk_flag=False, task_id="t_fail_001", session_id="s_test_001", duration=0.5)
    result2 = dispatcher.report_failure(skill_id="test_fail_skill", failure_reason="timeout_error", risk_flag=True, task_id="t_fail_002", session_id="s_test_001", duration=2.0)
    print(f"  result1: {result1}")
    print(f"  result2: {result2}")
    outcome2 = result2.get("outcome", result2)
    assert outcome2.get("consecutive_failures", 0) >= 2
    print("  PASS")
    return True


def test_dispatch():
    print()
    print("=" * 60)
    print("  Test 3: FeedbackDispatcher.dispatch()")
    print("=" * 60)
    dispatcher = FeedbackDispatcher(phoenix_base_dir=PHOENIX_BASE, reporter_base_dir=PHOENIX_BASE, mode="sync")
    r1 = dispatcher.dispatch(skill_id="dt_skill", execution_result="success", task_id="t1", session_id="s1", duration=0.1)
    r2 = dispatcher.dispatch(skill_id="dt_skill", execution_result="failure", failure_reason="err", risk_flag=False, task_id="t2", session_id="s1", duration=0.1)
    r3 = dispatcher.dispatch(skill_id="", execution_result="skipped", reason="no_match", task_id="t3", session_id="s1", duration=0.0)
    print(f"  dispatch(success): {r1}")
    print(f"  dispatch(failure): {r2}")
    print(f"  dispatch(skipped): {r3}")
    assert r1.get("success") is True
    print("  PASS")
    return True


def test_thresholds():
    print()
    print("=" * 60)
    print("  Test 4: Threshold constants")
    print("=" * 60)
    print(f"  REPLAY={Threshold.CONSECUTIVE_FAILURES_FOR_REPLAY}, REVIEW={Threshold.CONSECUTIVE_FAILURES_FOR_REVIEW}, QUARANTINE={Threshold.RISK_INCIDENTS_FOR_QUARANTINE}")
    assert Threshold.CONSECUTIVE_FAILURES_FOR_REPLAY == 2
    assert Threshold.CONSECUTIVE_FAILURES_FOR_REVIEW == 3
    assert Threshold.RISK_INCIDENTS_FOR_QUARANTINE == 2
    print("  PASS")
    return True


def test_tracker():
    print()
    print("=" * 60)
    print("  Test 5: OutcomeTracker instantiation")
    print("=" * 60)
    tracker = OutcomeTracker(phoenix_base_dir=PHOENIX_BASE, reporter_base_dir=PHOENIX_BASE)
    print(f"  base_dir={tracker.base_dir}")
    print("  PASS")
    return True


def main():
    print("Phoenix-Evo V0.7 Feedback Dispatcher Test")
    print("=" * 60)
    tests = [test_report_success, test_report_failure, test_dispatch, test_thresholds, test_tracker]
    passed = failed = 0
    for fn in tests:
        try:
            if fn(): passed += 1
        except Exception as e:
            print(f"  FAILED: {e}")
            traceback.print_exc()
            failed += 1
    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("所有 V0.7 Feedback 测试通过！")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
