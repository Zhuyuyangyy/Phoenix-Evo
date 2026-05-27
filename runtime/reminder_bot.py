"""
Phoenix-Evo Self-Reminder Bot
用Phoenix-Evo自进化闭环做自我监督：每小时检查TODO，如有过期任务强制提醒

Usage:
  python3 reminder_bot.py [--check-only] [--force-remind]
"""

import sys
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

# Phoenix-Evo 路径
PHOENIX_BASE = Path("/mnt/d/ZYY Project/Phoenix-Evo")
sys.path.insert(0, str(PHOENIX_BASE))

PHOENIX_STORE = PHOENIX_BASE / "logs" / "outcome_tracker_store.json"
REMINDER_LOG = PHOENIX_BASE / "logs" / "reminder_log.jsonl"


def load_pending_tasks():
    """从Phoenix outcome_tracker加载未完成/进行中的任务"""
    pending = []
    if PHOENIX_STORE.exists():
        with open(PHOENIX_STORE) as f:
            store = json.load(f)
        for skill_id, state in store.items():
            if state.get("status") in ("pending", "flagged"):
                pending.append({
                    "skill_id": skill_id,
                    "status": state["status"],
                    "failures": state.get("failure_count", 0),
                    "consecutive": state.get("consecutive_failures", 0),
                    "last": state.get("last_outcome", "unknown"),
                })
    return pending


def load_reminder_history():
    """加载已提醒历史，避免重复催"""
    history = {}
    if REMINDER_LOG.exists():
        with open(REMINDER_LOG) as f:
            for line in f:
                try:
                    r = json.loads(line)
                    history[r["skill_id"]] = r["reminder_count"]
                except:
                    pass
    return history


def record_reminder(skill_id: str, message: str, count: int):
    """记录本次提醒"""
    with open(REMINDER_LOG, "a") as f:
        f.write(json.dumps({
            "skill_id": skill_id,
            "message": message,
            "reminder_count": count,
            "timestamp": datetime.now().isoformat(),
        }, ensure_ascii=False) + "\n")


def should_remind(skill_id: str, consecutive_failures: int, last_outcome: str) -> tuple:
    """
    判断是否需要提醒，返回 (should, reason, urgency)
    urgency: "high" / "medium" / "low"
    """
    if consecutive_failures >= 3:
        return True, f"连续失败{consecutive_failures}次，请分析根因", "high"
    if consecutive_failures >= 1 and last_outcome == "failure":
        return True, f"上次任务失败(consecutive={consecutive_failures})，建议修复", "medium"
    if "pending" in str(last_outcome):
        return True, "任务状态pending，请确认是否卡住", "medium"
    return False, "", "low"


def build_reminder_message(pending: list, history: dict) -> str:
    """生成提醒消息文本"""
    lines = []
    lines.append(f"\n{'='*50}")
    lines.append(f"🦅 [Phoenix Self-Reminder] {datetime.now().strftime('%H:%M')}")
    lines.append(f"{'='*50}")
    
    # 高优先级
    high = [p for p in pending if should_remind(p["skill_id"], p["consecutive"], p["last"])[2] == "high"]
    medium = [p for p in pending if should_remind(p["skill_id"], p["consecutive"], p["last"])[2] == "medium"]
    
    if not pending:
        lines.append("\n✅ 无积压任务，Phoenix运行正常")
        lines.append(f"{'='*50}\n")
        return "\n".join(lines)
    
    if high:
        lines.append(f"\n🚨 高优先级 ({len(high)}项):")
        for p in high:
            _, reason, _ = should_remind(p["skill_id"], p["consecutive"], p["last"])
            lines.append(f"  • [{p['skill_id']}] {reason}")
            lines.append(f"    consecutive_failures={p['consecutive']} last={p['last']}")
    
    if medium:
        lines.append(f"\n⚠️  中优先级 ({len(medium)}项):")
        for p in medium:
            _, reason, _ = should_remind(p["skill_id"], p["consecutive"], p["last"])
            lines.append(f"  • [{p['skill_id']}] {reason}")
    
    total_pending = len(pending)
    total_done = sum(1 for p in pending if p["last"] == "success")
    lines.append(f"\n📊 统计: 待处理={total_pending} 已解决={total_done}")
    lines.append(f"{'='*50}\n")
    return "\n".join(lines)


def phoenix_status_summary() -> str:
    """Phoenix运行时状态摘要"""
    try:
        from runtime import PhoenixRuntime
        from runtime.outcome_tracker import OutcomeTracker, OutcomeStatus
        runtime = PhoenixRuntime(base_dir=PHOENIX_BASE)
        
        # 用 PhoenixRuntime.query() 做自路由（体现 Phoenix 自进化闭环）
        result = runtime.query(
            task_description="检测 pending/flagged 任务并生成提醒",
            task_type="project_management",
            risk_level="low",
            session_id="reminder_internal",
        )
        
        # 自检后写回 outcome_tracker（reminder_bot 自管理）
        tracker = OutcomeTracker(phoenix_base_dir=PHOENIX_BASE)
        report = tracker.process_pending()
        
        router = runtime.router
        retriever = router.retriever
        
        summary = []
        summary.append(f"\n🔮 Phoenix-Evo Runtime Status [{datetime.now().strftime('%H:%M')}]:")
        summary.append(f"   Router: SkillRouter (base_dir={PHOENIX_BASE.name})")
        summary.append(f"   Runtime components: {len([c for c in dir(runtime) if not c.startswith('_')])}")
        summary.append(f"   Self-route result: skill_found={result.skill_found}")
        summary.append(f"   OutcomeTracker: processed={report.get('processed',0)}, curated={report.get('curated',0)}")
        return "\n".join(summary)
    except Exception as e:
        return f"\n🔮 Phoenix Status: error({e})"


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true", help="只检查不提醒")
    parser.add_argument("--force-remind", action="store_true", help="强制提醒")
    args = parser.parse_args()

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Phoenix Self-Reminder Check")
    
    pending = load_pending_tasks()
    history = load_reminder_history()
    
    summary = build_reminder_message(pending, history)
    print(summary)
    
    phoenix_status = phoenix_status_summary()
    print(phoenix_status)
    
    if args.check_only:
        print("[check-only mode, no reminder sent]")
        return
    
    # 对于高优先级，强制输出结构化提醒
    high = [p for p in pending if should_remind(p["skill_id"], p["consecutive"], p["last"])[2] == "high"]
    if high or args.force_remind:
        # 输出结构化提醒（供外部程序解析）
        print("\n[SELF_REMINDER]", file=sys.stderr)
        for p in high:
            count = history.get(p["skill_id"], 0) + 1
            record_reminder(p["skill_id"], f"High: consecutive={p['consecutive']}", count)
            print(f"SELF_REMINDER|high|{p['skill_id']}|consecutive_failures={p['consecutive']}", file=sys.stderr)
        print("[/SELF_REMINDER]", file=sys.stderr)


if __name__ == "__main__":
    main()