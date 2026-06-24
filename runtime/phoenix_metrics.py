"""
Phoenix-Evo V0.9 / V1.0 Metrics Collector
==========================================

Tracks all runtime and curation metrics for monitoring, alerting, and dashboards.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any


@dataclass
class TaskMetric:
    task_id: str
    skill_id: str
    state: str
    latency_ms: float
    timestamp: float


@dataclass
class CuratorMetric:
    run_id: str
    skills_scanned: int
    skills_updated: int
    skills_quarantined: int
    skills_activated: int
    duration_ms: float
    timestamp: float


class PhoenixMetrics:
    """Thread-safe metrics collector for Phoenix-Evo."""

    def __init__(self, phoenix_base_dir: Path | str):
        self.base_dir = Path(phoenix_base_dir)
        self._lock = Lock()
        self._total_tasks = 0
        self._tasks_by_state: dict = defaultdict(int)
        self._skill_usage: dict = defaultdict(int)
        self._curator_runs = 0
        self._quarantine_events = 0
        self._skill_success_rate: dict = {}
        self._skill_success_count: dict = defaultdict(int)
        self._skill_total_count: dict = defaultdict(int)
        self._latency_buckets: dict = defaultdict(list)
        self._last_scan_at: float | None = None
        self._last_outcome_process_at: float | None = None
        self._recent_tasks: list = []
        self._recent_curator_runs: list = []

    def record_task(self, ctx: Any) -> None:
        if isinstance(ctx, dict):
            task_id = ctx.get("task_id", "?")
            skill_id = ctx.get("skill_id", "?")
            state = ctx.get("state", "unknown")
            latency_ms = float(ctx.get("latency_ms", 0.0))
        else:
            task_id = getattr(ctx, "task_id", "?")
            skill_id = getattr(ctx, "skill_id", "?")
            state = getattr(ctx, "state", "unknown")
            latency_ms = float(getattr(ctx, "latency_ms", 0.0))

        with self._lock:
            self._total_tasks += 1
            self._tasks_by_state[state] += 1
            self._skill_usage[skill_id] += 1
            self._skill_total_count[skill_id] += 1
            if state == "success":
                self._skill_success_count[skill_id] += 1
            total = self._skill_total_count[skill_id]
            self._skill_success_rate[skill_id] = self._skill_success_count[skill_id] / total
            self._latency_buckets[skill_id].append(latency_ms)
            self._recent_tasks.append(TaskMetric(
                task_id=str(task_id), skill_id=str(skill_id),
                state=str(state), latency_ms=float(latency_ms), timestamp=time.time()
            ))
            if len(self._recent_tasks) > 1000:
                self._recent_tasks.pop(0)

    def record_curator_run(self, report: Any) -> None:
        if isinstance(report, dict):
            run_id = report.get("run_id", "?")
            skills_scanned = int(report.get("skills_scanned", 0))
            skills_updated = int(report.get("skills_updated", 0))
            skills_quarantined = int(report.get("skills_quarantined", 0))
            skills_activated = int(report.get("skills_activated", 0))
            duration_ms = float(report.get("duration_ms", 0.0))
        else:
            run_id = getattr(report, "run_id", "?")
            skills_scanned = int(getattr(report, "skills_scanned", 0))
            skills_updated = int(getattr(report, "skills_updated", 0))
            skills_quarantined = int(getattr(report, "skills_quarantined", 0))
            skills_activated = int(getattr(report, "skills_activated", 0))
            duration_ms = float(getattr(report, "duration_ms", 0.0))

        with self._lock:
            self._curator_runs += 1
            self._quarantine_events += skills_quarantined
            self._last_scan_at = time.time()
            self._recent_curator_runs.append(CuratorMetric(
                run_id=str(run_id), skills_scanned=skills_scanned, skills_updated=skills_updated,
                skills_quarantined=skills_quarantined, skills_activated=skills_activated,
                duration_ms=duration_ms, timestamp=time.time()
            ))
            if len(self._recent_curator_runs) > 100:
                self._recent_curator_runs.pop(0)

    def record_outcome_process(self) -> None:
        with self._lock:
            self._last_outcome_process_at = time.time()

    def get_metrics(self) -> dict:
        with self._lock:
            return {
                "total_tasks": self._total_tasks,
                "tasks_by_state": dict(self._tasks_by_state),
                "skill_usage": dict(self._skill_usage),
                "skill_success_rate": dict(self._skill_success_rate),
                "skill_total_count": dict(self._skill_total_count),
                "skill_success_count": dict(self._skill_success_count),
                "avg_latency_ms": {s: round(sum(v) / len(v), 2) if v else 0.0 for s, v in self._latency_buckets.items()},
                "curator_runs": self._curator_runs,
                "quarantine_events": self._quarantine_events,
                "last_scan_at": datetime.fromtimestamp(self._last_scan_at).isoformat() if self._last_scan_at else None,
                "last_outcome_process_at": datetime.fromtimestamp(self._last_outcome_process_at).isoformat() if self._last_outcome_process_at else None,
            }

    def get_skill_health(self) -> dict:
        with self._lock:
            health = {}
            for sid in self._skill_usage:
                recent = [t for t in self._recent_tasks if t.skill_id == sid][-20:]
                rate = self._skill_success_rate.get(sid, 0.0)
                avg_lat = round(sum(t.latency_ms for t in recent) / len(recent), 2) if recent else 0.0
                health[sid] = {
                    "total_runs": self._skill_total_count.get(sid, 0),
                    "success_count": self._skill_success_count.get(sid, 0),
                    "success_rate": round(rate, 4),
                    "avg_latency_ms": avg_lat,
                    "recent_states": [t.state for t in recent],
                    "health_score": self._calc_health_score(rate, len(recent)),
                }
            return health

    def _calc_health_score(self, rate: float, samples: int) -> str:
        if samples < 3:
            return "insufficient_data"
        if rate >= 0.95:
            return "excellent"
        if rate >= 0.80:
            return "good"
        if rate >= 0.60:
            return "fair"
        return "poor"

    def _overall_sr(self, m: dict) -> float:
        nontrivial = sum(v for k, v in m["tasks_by_state"].items() if k != "unknown")
        if nontrivial == 0:
            return 0.0
        return m["tasks_by_state"].get("success", 0) / nontrivial

    def _total_nontrivial(self, m: dict) -> int:
        return sum(v for k, v in m["tasks_by_state"].items() if k != "unknown")

    def export_prometheus(self) -> str:
        m = self.get_metrics()
        parts = [
            "# HELP phoenix_total_tasks Total tasks processed",
            "# TYPE phoenix_total_tasks counter",
            "phoenix_total_tasks " + str(m["total_tasks"]),
            "",
            "# HELP phoenix_tasks_by_state Tasks per state",
            "# TYPE phoenix_tasks_by_state counter",
        ]
        for state, count in m["tasks_by_state"].items():
            parts.append("phoenix_tasks_by_state{state=\"" + state + "\"} " + str(count))
        parts += [
            "",
            "phoenix_curator_runs_total " + str(m["curator_runs"]),
            "phoenix_quarantine_events_total " + str(m["quarantine_events"]),
        ]
        for sid, rate in m["skill_success_rate"].items():
            parts.append("phoenix_skill_success_rate{skill_id=\"" + sid + "\"} " + (f"{rate:.4f}"))
        for sid, latency in m.get("avg_latency_ms", {}).items():
            parts.append("phoenix_avg_latency_ms{skill_id=\"" + sid + "\"} " + str(latency))
        for sid, usage in m["skill_usage"].items():
            parts.append("phoenix_skill_usage_total{skill_id=\"" + sid + "\"} " + str(usage))
        return "\n".join(parts)

    def generate_html_dashboard(self) -> str:
        m = self.get_metrics()
        health = self.get_skill_health()
        score_colors = {
            "excellent": "#22c55e", "good": "#84cc16",
            "fair": "#eab308", "poor": "#ef4444",
            "insufficient_data": "#9ca3af",
        }

        rows = ""
        for sid, h in health.items():
            color = score_colors.get(h["health_score"], "#9ca3af")
            rows += (
                "<tr><td><code>" + str(sid) + "</code></td>"
                "<td>" + str(h["total_runs"]) + "</td>"
                "<td>" + str(h["success_count"]) + "</td>"
                "<td style=\"color:" + color + ";font-weight:bold\">" + h["health_score"] + "</td>"
                "<td>" + ("%.1f%%" % (h["success_rate"] * 100)) + "</td>"
                "<td>" + ("{:.1f}ms".format(h["avg_latency_ms"])) + "</td></tr>"
            )
        if not rows:
            rows = "<tr><td colspan=\"6\" style=\"text-align:center;color:#64748b\">No skill data yet</td></tr>"

        state_labels = list(m["tasks_by_state"].keys())
        state_values = list(m["tasks_by_state"].values())
        sc_map = {"success": "#22c55e", "failure": "#ef4444", "skipped": "#f59e0b", "unknown": "#9ca3af"}

        pie_labels = "[" + ",".join('"' + l + '"' for l in state_labels) + "]"
        pie_data = "[" + ",".join(str(v) for v in state_values) + "]"
        pie_colors = "[" + ",".join('"' + sc_map.get(l, "#9ca3af") + '"' for l in state_labels) + "]"

        lat_keys = m.get("avg_latency_ms", {}).keys()
        lat_vals = m.get("avg_latency_ms", {}).values()
        lat_labels = "[" + ",".join('"' + s + '"' for s in lat_keys) + "]"
        lat_data = "[" + ",".join(str(v) for v in lat_vals) + "]"

        overall_rate = self._overall_sr(m)
        total_nontrivial = self._total_nontrivial(m)
        success_count = m["tasks_by_state"].get("success", 0)
        total_tasks = m["total_tasks"]
        active_skills = len(m["skill_usage"])
        curator_runs = m["curator_runs"]
        quarantine_events = m["quarantine_events"]
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return (
            '<!DOCTYPE html><html lang="en">'
            '<head><meta charset="utf-8">'
            '<title>Phoenix-Evo Metrics</title>'
            '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>'
            '<style>'
            'body{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:20px}'
            'h1{color:#f8fafc;margin-bottom:4px}'
            '.subtitle{color:#94a3b8;margin-bottom:24px;font-size:14px}'
            '.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;margin-bottom:24px}'
            '.card{background:#1e293b;border-radius:12px;padding:20px;border:1px solid #334155}'
            '.card h3{margin:0 0 8px;color:#94a3b8;font-size:13px;text-transform:uppercase}'
            '.card .val{font-size:36px;font-weight:700;color:#f8fafc}'
            '.card .sub{font-size:12px;color:#64748b;margin-top:4px}'
            'table{width:100%;border-collapse:collapse;font-size:14px}'
            'th{text-align:left;padding:10px 12px;border-bottom:1px solid #334155;color:#94a3b8;font-size:12px;text-transform:uppercase}'
            'td{padding:10px 12px;border-bottom:1px solid #1e293b}'
            'tr:hover td{background:#1e293b}'
            'code{background:#334155;padding:2px 6px;border-radius:4px;font-size:13px}'
            '.charts{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px}'
            'canvas{background:#1e293b;border-radius:8px;padding:12px}'
            '</style></head>'
            '<body>'
            '<h1>Phoenix-Evo Metrics</h1>'
            '<div class="subtitle">V1.0 - ' + ts + '</div>'
            '<div class="grid">'
            '<div class="card"><h3>Total Tasks</h3><div class="val">' + str(total_tasks) + '</div></div>'
            '<div class="card"><h3>Success Rate</h3><div class="val">' + ("%.1f%%" % (overall_rate * 100)) + '</div>'
            '<div class="sub">' + str(success_count) + '/' + str(total_nontrivial) + ' successful</div></div>'
            '<div class="card"><h3>Curator Runs</h3><div class="val">' + str(curator_runs) + '</div>'
            '<div class="sub">' + str(quarantine_events) + ' quarantine events</div></div>'
            '<div class="card"><h3>Active Skills</h3><div class="val">' + str(active_skills) + '</div>'
            '<div class="sub">tracked in metrics</div></div>'
            '</div>'
            '<div class="charts">'
            '<canvas id="stateChart"></canvas><canvas id="latencyChart"></canvas>'
            '</div>'
            '<h2 style="color:#f8fafc;margin-bottom:12px">Skill Health</h2>'
            '<table>'
            '<thead><tr><th>Skill</th><th>Total</th><th>Success</th><th>Health</th><th>Rate</th><th>Avg Latency</th></tr></thead>'
            '<tbody>' + rows + '</tbody></table>'
            '<script>'
            'new Chart(document.getElementById("stateChart"),{'
            'type:"doughnut",data:{labels:' + pie_labels + ',datasets:[{data:' + pie_data + ',backgroundColor:' + pie_colors + ',borderWidth:0}]},'
            'options:{responsive:true,plugins:{legend:{position:"bottom",labels:{color:"#94a3b8"}}}}'
            '});'
            'new Chart(document.getElementById("latencyChart"),{'
            'type:"bar",data:{labels:' + lat_labels + ',datasets:[{label:"Avg Latency (ms)",data:' + lat_data + ',backgroundColor:"#3b82f6"}]},'
            'options:{responsive:true,plugins:{legend:{labels:{color:"#94a3b8"}}}},'
            'scales:{x:{ticks:{color:"#94a3b8"},grid:{color:"#1e293b"}},y:{ticks:{color:"#94a3b8"},grid:{color:"#1e293b"}}}}'
            '});'
            '</script></body></html>'
        )

    def reset(self) -> None:
        with self._lock:
            self._total_tasks = 0
            self._tasks_by_state.clear()
            self._skill_usage.clear()
            self._curator_runs = 0
            self._quarantine_events = 0
            self._skill_success_rate.clear()
            self._skill_success_count.clear()
            self._skill_total_count.clear()
            self._latency_buckets.clear()
            self._last_scan_at = None
            self._last_outcome_process_at = None
            self._recent_tasks.clear()
            self._recent_curator_runs.clear()


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        metrics = PhoenixMetrics(Path(tmpdir))

        class MockCtx:
            def __init__(self, task_id, skill_id, state, latency_ms):
                self.task_id = task_id
                self.skill_id = skill_id
                self.state = state
                self.latency_ms = latency_ms

        for i in range(20):
            state = "success" if i % 5 != 0 else "failure"
            metrics.record_task(MockCtx("task-" + str(i), "code-review", state, 120.5 + i * 2))
        for i in range(5):
            metrics.record_task(MockCtx("task-doc-" + str(i), "doc-write", "success", 80.0))

        class MockReport:
            run_id = "run-001"
            skills_scanned = 12
            skills_updated = 3
            skills_quarantined = 1
            skills_activated = 2
            duration_ms = 450.0

        metrics.record_curator_run(MockReport())

        print("=== get_metrics() ===")
        m = metrics.get_metrics()
        for k, v in m.items():
            if k != "recent_tasks":
                print(" ", k, ":", v)

        print("\n=== skill_health ===")
        print(metrics.get_skill_health())

        print("\n=== prometheus export ===")
        print(metrics.export_prometheus())

        html = metrics.generate_html_dashboard()
        out = Path(tmpdir) / "dashboard.html"
        out.write_text(html, encoding="utf-8")
        print("\nDashboard written to:", out)
