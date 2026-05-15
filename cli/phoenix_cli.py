# -*- coding: utf-8 -*-
"""
Phoenix-Evo V1.0 PhoenixCLI
============================
Command-line interface for Phoenix-Evo operations.

Subcommands:
  status                   — Show PhoenixEvo system status
  skills list [--status]   — List skills
  skills activate <id>     — Activate a draft skill
  quarantine review         — Show quarantine queue
  quarantine resolve <id>   — Resolve a quarantined skill
  curator run [--scan-only]— Run curator scan
  daemon start/stop/status — Manage daemon
  metrics [--format]       — Show metrics
  replay <task_id>         — Replay a task trajectory

Usage:
    python -m cli.phoenix_cli status --base-dir /path/to/Phoenix-Evo
    python -m cli.phoenix_cli skills list --base-dir /path/to/Phoenix-Evo
    python -m cli.phoenix_cli daemon start --base-dir /path/to/Phoenix-Evo
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional

# ANSI color codes (no external deps)
C = type("C", (), {
    "reset": "\033[0m", "bold": "\033[1m", "dim": "\033[2m",
    "red": "\033[91m", "green": "\033[92m", "yellow": "\033[93m",
    "blue": "\033[94m", "magenta": "\033[95m", "cyan": "\033[96m",
    "white": "\033[97m",
})()


def color(text: str, c: str) -> str:
    return f"{c}{text}{C.reset}"


def section(title: str) -> None:
    print(f"\n{color('══ ' + title + ' ', C.cyan,)}{color('═' * (60 - len(title)), C.dim)}")


def kv(key: str, value: str, ok: bool = True) -> None:
    icon = color("✓", C.green) if ok else color("✗", C.red)
    print(f"  {icon} {color(key.ljust(28), C.bold)} {value}")


def kv_section(d: dict, indent: int = 2) -> None:
    for k, v in d.items():
        prefix = " " * indent
        if isinstance(v, dict):
            print(f"{prefix}{color(k, C.bold)}:")
            kv_section(v, indent + 4)
        elif isinstance(v, list):
            print(f"{prefix}{color(k, C.bold)}: {len(v)} items")
        else:
            print(f"{prefix}{k}: {v}")


# ─────────────────────────────────────────────────────────────
# Core Imports (lazy to avoid import errors when modules are missing)
# ─────────────────────────────────────────────────────────────

def get_phoenix():
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from core.phoenix_evo import PhoenixEvo
    return PhoenixEvo


def get_phoenix_metrics():
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from runtime.phoenix_metrics import PhoenixMetrics
    return PhoenixMetrics


def get_phoenix_daemon():
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from runtime.phoenix_daemon import PhoenixRuntimeDaemon
    return PhoenixRuntimeDaemon


# ─────────────────────────────────────────────────────────────
# Subcommand: status
# ─────────────────────────────────────────────────────────────

def cmd_status(args) -> int:
    PhoenixEvo = get_phoenix()
    try:
        phoenix = PhoenixEvo.load(args.base_dir)
    except FileNotFoundError:
        phoenix = PhoenixEvo.from_scratch(args.base_dir)
        print(color("  [NEW] Phoenix-Evo initialized (no prior state found)", C.yellow))
    except Exception as ex:
        print(color(f"  [ERROR] Failed to load PhoenixEvo: {ex}", C.red))
        return 1

    status = phoenix.get_status()
    health = phoenix.get_health_summary()

    section("Phoenix-Evo System Status")
    kv("Version", status.get("version", "unknown"))
    kv("Base directory", str(args.base_dir))
    kv("Skills (total)", str(status.get("skills_total", 0)))
    kv("Skills (active)", str(status.get("skills_active", 0)))
    kv("Skills (draft)", str(status.get("skills_draft", 0)))
    kv("Quarantine queue", str(status.get("quarantine_pending", 0)))
    kv("Trajectories logged", str(status.get("trajectories_logged", 0)))
    kv("Curator last run", status.get("curator_last_run", "never") or "never")
    kv("Daemon", status.get("daemon_running", "stopped"))

    section("Health Summary")
    for rec in health.get("recommendations", []):
        icon = {"critical": color("✗", C.red), "warning": color("!", C.yellow), "info": color("i", C.blue)}.get(
            rec.get("severity", "info"), "i"
        )
        print(f"  {icon} [{rec.get('severity','?').upper()}] {rec.get('message','')}")

    if args.json:
        print("\n" + json.dumps({"status": status, "health": health}, indent=2, default=str))

    return 0


# ─────────────────────────────────────────────────────────────
# Subcommand: skills list
# ─────────────────────────────────────────────────────────────

def cmd_skills_list(args) -> int:
    PhoenixEvo = get_phoenix()
    try:
        phoenix = PhoenixEvo.load(args.base_dir)
    except FileNotFoundError:
        phoenix = PhoenixEvo.from_scratch(args.base_dir)
    except Exception as ex:
        print(color(f"[ERROR] {ex}", C.red))
        return 1

    skills = phoenix.skills
    if args.status:
        filter_status = args.status.lower()
        filtered = {k: v for k, v in skills.items() if v.get("status") == filter_status}
        print(f"  Showing {color(filter_status, C.cyan)} skills only ({len(filtered)}/{len(skills)})")
        skills = filtered

    section(f"Skills ({len(skills)} total)")
    for sid, sinfo in sorted(skills.items()):
        status = sinfo.get("status", "?")
        status_color = {"active": C.green, "draft": C.yellow, "quarantine": C.red}.get(status, C.white)
        success_rate = sinfo.get("success_rate", None)
        rate_str = f"{success_rate:.1%}" if success_rate is not None else "N/A"
        print(f"  {color(sid, C.bold)}  [{color(status, status_color)}]  success={rate_str}  "
              f"runs={sinfo.get('total_runs',0)}")

    return 0


# ─────────────────────────────────────────────────────────────
# Subcommand: skills activate
# ─────────────────────────────────────────────────────────────

def cmd_skills_activate(args) -> int:
    PhoenixEvo = get_phoenix()
    try:
        phoenix = PhoenixEvo.load(args.base_dir)
    except Exception as ex:
        print(color(f"[ERROR] {ex}", C.red))
        return 1

    skill = phoenix.skills.get(args.skill_id)
    if not skill:
        print(color(f"[ERROR] Skill '{args.skill_id}' not found", C.red))
        return 1

    if skill.get("status") == "active":
        print(color(f"[OK] Skill '{args.skill_id}' is already active", C.green))
        return 0

    skill["status"] = "active"
    phoenix.save()
    print(color(f"[OK] Skill '{args.skill_id}' activated", C.green))
    return 0


# ─────────────────────────────────────────────────────────────
# Subcommand: quarantine review
# ─────────────────────────────────────────────────────────────

def cmd_quarantine_review(args) -> int:
    PhoenixEvo = get_phoenix()
    try:
        phoenix = PhoenixEvo.load(args.base_dir)
    except Exception as ex:
        print(color(f"[ERROR] {ex}", C.red))
        return 1

    quarantine = phoenix.quarantine_manager.list_quarantined()
    if not quarantine:
        print(color("  Quarantine queue is empty", C.green))
        return 0

    section(f"Quarantine Queue ({len(quarantine)} items)")
    for item in quarantine:
        skill_id = item.get("skill_id", "?")
        reason = item.get("reason", "?")
        quarantined_at = item.get("quarantined_at", "?")
        print(f"  {color(skill_id, C.red, C.bold)}  reason={reason}  at={quarantined_at}")

    return 0


# ─────────────────────────────────────────────────────────────
# Subcommand: quarantine resolve
# ─────────────────────────────────────────────────────────────

def cmd_quarantine_resolve(args) -> int:
    PhoenixEvo = get_phoenix()
    try:
        phoenix = PhoenixEvo.load(args.base_dir)
    except Exception as ex:
        print(color(f"[ERROR] {ex}", C.red))
        return 1

    skill = phoenix.skills.get(args.skill_id)
    if not skill:
        print(color(f"[ERROR] Skill '{args.skill_id}' not found", C.red))
        return 1

    action = args.action.lower()
    if action == "activate":
        skill["status"] = "active"
        phoenix.save()
        print(color(f"[OK] Skill '{args.skill_id}' activated from quarantine", C.green))
    elif action == "archive":
        skill["status"] = "archived"
        phoenix.save()
        print(color(f"[OK] Skill '{args.skill_id}' archived", C.blue))
    elif action == "reject":
        # Remove from skills entirely
        del phoenix.skills[args.skill_id]
        phoenix.save()
        print(color(f"[OK] Skill '{args.skill_id}' rejected and removed", C.yellow))
    else:
        print(color(f"[ERROR] Unknown action '{action}'", C.red))
        return 1

    return 0


# ─────────────────────────────────────────────────────────────
# Subcommand: curator run
# ─────────────────────────────────────────────────────────────

def cmd_curator_run(args) -> int:
    sys.path.insert(0, str(args.base_dir))
    try:
        from core.skill_curator import SkillCurator
    except Exception as ex:
        print(color(f"[ERROR] Failed to import SkillCurator: {ex}", C.red))
        return 1

    print(color("Running curator scan...", C.cyan))
    try:
        curator = SkillCurator(phoenix_base_dir=args.base_dir)
        report = curator.scan()
        print(color(f"[OK] Scan complete", C.green))
        kv("Skills scanned", str(report.skills_scanned))
        kv("Skills updated", str(report.skills_updated))
        kv("Skills quarantined", str(report.skills_quarantined))
        kv("Skills activated", str(report.skills_activated))
        kv("Duration", f"{report.duration_ms:.1f}ms")
    except Exception as ex:
        print(color(f"[ERROR] Curator scan failed: {ex}", C.red))
        return 1

    return 0


# ─────────────────────────────────────────────────────────────
# Subcommand: daemon
# ─────────────────────────────────────────────────────────────

def cmd_daemon(args) -> int:
    PhoenixDaemon = get_phoenix_daemon()
    sub = args.daemon_cmd

    if sub == "start":
        daemon = PhoenixDaemon(
            phoenix_base_dir=args.base_dir,
            check_interval=args.check_interval,
            curator_interval=args.curator_interval,
        )
        daemon.start()
        print(color(f"[OK] PhoenixRuntimeDaemon started", C.green))
        print(f"  OutcomeTracker interval: {args.check_interval}s")
        print(f"  SkillCurator interval: {args.curator_interval}s")
        try:
            while daemon.is_running():
                time.sleep(5)
        except KeyboardInterrupt:
            daemon.stop()
        return 0

    elif sub == "stop":
        daemon = PhoenixDaemon(phoenix_base_dir=args.base_dir)
        daemon.stop()
        print(color("[OK] PhoenixRuntimeDaemon stopped", C.green))
        return 0

    elif sub == "status":
        daemon = PhoenixDaemon(phoenix_base_dir=args.base_dir)
        running = daemon.is_running()
        if running:
            print(color(f"[RUNNING] Uptime: {daemon.uptime_seconds:.0f}s", C.green))
        else:
            print(color("[STOPPED]", C.yellow))
        return 0

    else:
        print(color(f"[ERROR] Unknown daemon subcommand: {sub}", C.red))
        return 1


# ─────────────────────────────────────────────────────────────
# Subcommand: metrics
# ─────────────────────────────────────────────────────────────

def cmd_metrics(args) -> int:
    PhoenixMetrics = get_phoenix_metrics()
    metrics = PhoenixMetrics(phoenix_base_dir=args.base_dir)

    if args.format == "prometheus":
        print(metrics.export_prometheus())
    elif args.format == "html":
        html = metrics.generate_html_dashboard()
        out = Path(args.base_dir) / "metrics_dashboard.html"
        out.write_text(html, encoding="utf-8")
        print(color(f"[OK] Dashboard written to {out}", C.green))
    else:
        print(json.dumps(metrics.get_metrics(), indent=2, default=str))

    return 0


# ─────────────────────────────────────────────────────────────
# Subcommand: replay
# ─────────────────────────────────────────────────────────────

def cmd_replay(args) -> int:
    sys.path.insert(0, str(args.base_dir))
    try:
        from core.replay_manager import ReplayManager
    except ImportError:
        print(color("[ERROR] ReplayManager not yet implemented", C.red))
        return 1

    try:
        manager = ReplayManager(phoenix_base_dir=args.base_dir)
        # Mock execute_fn (does nothing — real replay would call actual tools)
        def mock_execute_fn(step):
            return {"ok": True, "output": "mock"}

        result = manager.replay(args.task_id, execute_fn=mock_execute_fn)
        print(color(f"[REPLAY] task_id={result.task_id}", C.cyan))
        print(f"  Original: {result.original_success}  Replay: {result.replay_success}")
        print(f"  Verdict: {color(result.verdict, C.green if result.verdict=='pass' else C.red)}")
        print(f"  Notes: {result.notes}")
        return 0 if result.verdict == "pass" else 1
    except Exception as ex:
        print(color(f"[ERROR] Replay failed: {ex}", C.red))
        return 1


# ─────────────────────────────────────────────────────────────
# Argument Parser
# ─────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="phoenix",
        description=color("Phoenix-Evo V1.0 — Self-Evolving Agent System", C.cyan),
    )
    parser.add_argument("--base-dir", type=Path, required=True, help="Phoenix-Evo base directory")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    sub = parser.add_subparsers(dest="command", required=True)

    # status
    sub.add_parser("status", help="Show PhoenixEvo system status")

    # skills
    skills_parser = sub.add_parser("skills", help="Skill management")
    skills_sub = skills_parser.add_subparsers(dest="skills_cmd", required=True)

    list_parser = skills_sub.add_parser("list", help="List all skills")
    list_parser.add_argument("--status", choices=["active", "draft", "quarantine"], help="Filter by status")

    activate_parser = skills_sub.add_parser("activate", help="Activate a draft skill")
    activate_parser.add_argument("skill_id", help="Skill ID to activate")

    # quarantine
    q_parser = sub.add_parser("quarantine", help="Quarantine management")
    q_sub = q_parser.add_subparsers(dest="q_cmd", required=True)
    q_sub.add_parser("review", help="Show quarantine queue")
    resolve_parser = q_sub.add_parser("resolve", help="Resolve a quarantined skill")
    resolve_parser.add_argument("skill_id", help="Skill ID to resolve")
    resolve_parser.add_argument("--action", choices=["activate", "archive", "reject"],
                                 default="activate", help="Resolution action")

    # curator
    curator_parser = sub.add_parser("curator", help="Run curator scan")
    curator_parser.add_argument("--scan-only", action="store_true", help="Scan only, no auto-actions")

    # daemon
    daemon_parser = sub.add_parser("daemon", help="Manage PhoenixRuntimeDaemon")
    daemon_sub = daemon_parser.add_subparsers(dest="daemon_cmd", required=True)
    start_parser = daemon_sub.add_parser("start", help="Start daemon")
    start_parser.add_argument("--check-interval", type=int, default=300)
    start_parser.add_argument("--curator-interval", type=int, default=3600)
    daemon_sub.add_parser("stop", help="Stop daemon")
    daemon_sub.add_parser("status", help="Check daemon status")

    # metrics
    metrics_parser = sub.add_parser("metrics", help="Show metrics")
    metrics_parser.add_argument("--format", choices=["json", "prometheus", "html"],
                                 default="json", help="Output format")

    # replay
    replay_parser = sub.add_parser("replay", help="Replay a task trajectory")
    replay_parser.add_argument("task_id", help="Task ID to replay")

    return parser


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "status":
        return cmd_status(args)
    elif args.command == "skills":
        if args.skills_cmd == "list":
            return cmd_skills_list(args)
        elif args.skills_cmd == "activate":
            return cmd_skills_activate(args)
    elif args.command == "quarantine":
        if args.q_cmd == "review":
            return cmd_quarantine_review(args)
        elif args.q_cmd == "resolve":
            return cmd_quarantine_resolve(args)
    elif args.command == "curator":
        return cmd_curator_run(args)
    elif args.command == "daemon":
        return cmd_daemon(args)
    elif args.command == "metrics":
        return cmd_metrics(args)
    elif args.command == "replay":
        return cmd_replay(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
