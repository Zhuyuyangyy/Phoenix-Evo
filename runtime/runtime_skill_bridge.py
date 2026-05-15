# -*- coding: utf-8 -*-
"""runtime_skill_bridge.py — Phoenix-Evo V0.8 Hermes Runtime Bridge"""
from __future__ import annotations
import logging, time, uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("runtime_skill_bridge")

class BridgeTaskState(str, Enum):
    INITIALIZING = "initializing"
    RETRIEVING = "retrieving"
    FILTERING = "filtering"
    INJECTING = "injecting"
    READY = "ready"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class BridgeTaskContext:
    task_id: str
    session_id: str
    task_description: str
    task_type: Optional[str] = None
    risk_level: str = "low"
    state: BridgeTaskState = BridgeTaskState.INITIALIZING
    matched_skills: list = field(default_factory=list)
    allowed_skills: list = field(default_factory=list)
    injected_context: str = ""
    candidates_summary: str = ""
    execution_result: Optional[str] = None
    failure_reason: Optional[str] = None
    duration_seconds: float = 0.0
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    ended_at: Optional[str] = None

    @property
    def has_safe_skill(self) -> bool:
        return len(self.allowed_skills) > 0

    @property
    def best_skill(self) -> Optional[dict]:
        return self.allowed_skills[0] if self.allowed_skills else None

    @property
    def is_ready(self) -> bool:
        return self.state == BridgeTaskState.READY

    def to_hermes_system_context(self) -> str:
        if not self.injected_context: return ""
        parts = ["## Relevant Phoenix Skills", "", self.injected_context, "",
                 "---",
                 "*Skill context is advisory only. Do not execute destructive operations without validation.*"]
        return chr(10).join(parts)

    def to_summary_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "task_description": self.task_description[:60]+"..." if len(self.task_description)>60 else self.task_description,
            "state": self.state.value,
            "matched_count": len(self.matched_skills),
            "allowed_count": len(self.allowed_skills),
            "has_safe_skill": self.has_safe_skill,
            "best_skill_name": self.allowed_skills[0].get("skill_name","?") if self.allowed_skills else "none",
            "duration_seconds": round(self.duration_seconds, 2),
        }

class HermesRuntimeBridge:
    def __init__(self, phoenix_base_dir: Optional[str] = None, outcome_store: Optional[dict] = None):
        self.base_dir = Path(phoenix_base_dir or Path(__file__).parent.parent)
        self._outcome_store = outcome_store or {}
        self._retriever = self._policy = self._injector = self._dispatcher = None

    @property
    def retriever(self):
        if self._retriever is None:
            from runtime.skill_retriever import SkillRetriever
            self._retriever = SkillRetriever(base_dir=self.base_dir)
        return self._retriever

    @property
    def policy(self):
        if self._policy is None:
            from runtime.skill_injection_policy import SafeInjectionPolicy
            self._policy = SafeInjectionPolicy()
        return self._policy

    @property
    def injector(self):
        if self._injector is None:
            from runtime.context_injector import ContextInjector
            self._injector = ContextInjector()
        return self._injector

    @property
    def dispatcher(self):
        if self._dispatcher is None:
            from runtime.feedback_dispatcher import FeedbackDispatcher
            self._dispatcher = FeedbackDispatcher(phoenix_base_dir=self.base_dir, reporter_base_dir=self.base_dir, mode="sync")
        return self._dispatcher

    def on_task_start(self, task_description: str, task_type: Optional[str] = None,
                      risk_level: str = "low", session_id: Optional[str] = None,
                      task_id: Optional[str] = None, max_candidates: int = 5) -> BridgeTaskContext:
        task_id = task_id or f"bridge_{uuid.uuid4().hex[:8]}"
        session_id = session_id or f"sess_{uuid.uuid4().hex[:8]}"
        ctx = BridgeTaskContext(task_id=task_id, session_id=session_id,
                                task_description=task_description, task_type=task_type,
                                risk_level=risk_level, state=BridgeTaskState.INITIALIZING)
        start_time = time.time()
        ctx.state = BridgeTaskState.RETRIEVING
        try:
            candidates = self.retriever.retrieve(task_description=task_description,
                                                  task_type=task_type, top_k=max_candidates)
            # matched_skills stores flattened index_entry data (so evidence_score is accessible)
            ctx.matched_skills = []
            for c in candidates:
                if isinstance(c, dict):
                    ie = c.get("index_entry", {})
                    flat = dict(ie)
                    flat["skill_id"] = c.get("skill_id", ie.get("skill_id", ""))
                    flat["relevance_score"] = c.get("relevance_score", 0.0)
                    flat["skill_name"] = ie.get("skill_name", c.get("skill_name", ""))
                    flat["evidence_score"] = ie.get("evidence_score", 0.0)
                    flat["task_type"] = ie.get("task_type", c.get("task_type", ""))
                    flat["status"] = ie.get("status", "active")
                    ctx.matched_skills.append(flat)
                else:
                    ctx.matched_skills.append(c if isinstance(c, dict) else {})
        except Exception as e:
            logger.warning("[Bridge] SkillRetriever failed: %s", e)
            ctx.matched_skills = []
        if not ctx.matched_skills:
            ctx.state = BridgeTaskState.READY
            ctx.candidates_summary = "No matching skills found"
            return ctx
        ctx.state = BridgeTaskState.FILTERING
        filtered = self.policy.filter_batch(skill_entries=ctx.matched_skills,
                                            task_type=task_type, task_risk=risk_level,
                                            outcome_store=self._outcome_store)
        allowed = [r for r in filtered if r.decision.value in ("allow", "defer")]
        ctx.allowed_skills = [{"skill_id": r.skill_id, "skill_name": r.skill_name,
                               "decision": r.decision.value, "reason": r.final_reason} for r in allowed]
        icon_map = {"allow": "ALLOW", "defer": "DEFER", "deny": "DENY", "review": "REVIEW"}
        parts = []
        for r in filtered[:3]:
            icon = icon_map.get(r.decision.value, "?")
            parts.append("[" + icon + "] " + r.skill_name + ": " + r.final_reason)
        ctx.candidates_summary = "; ".join(parts) if parts else "no candidates"
        ctx.state = BridgeTaskState.INJECTING
        if allowed:
            top = allowed[0]
            sid = top.skill_id
            card = self._load_skill_card(sid)
            entry = next((e for e in ctx.matched_skills if e.get("skill_id") == sid), {})
            class _FakeRouteResult:
                def __init__(self2, e, c, sid, sname):
                    self2._index_entry = e; self2._skill_card = c
                    self2.skill_id = sid; self2.skill_name = sname
                    self2.route_score = 0.8
                    self2.evidence_score = entry.get("evidence_score", 0.0)
                    self2.replay_pass_rate = entry.get("replay_pass_rate", 0.0)
            fake_rr = _FakeRouteResult(entry, card, sid, top.skill_name)
            ctx.injected_context = self.injector.inject(skill=fake_rr)
        ctx.state = BridgeTaskState.READY
        ctx.duration_seconds = time.time() - start_time
        return ctx

    def on_task_complete(self, ctx: BridgeTaskContext, execution_result: str = "success",
                         duration: Optional[float] = None) -> None:
        ctx.ended_at = datetime.now().isoformat()
        if duration is not None: ctx.duration_seconds = duration
        ctx.state = BridgeTaskState.SUCCESS if execution_result == "success" else BridgeTaskState.FAILED
        ctx.execution_result = execution_result
        for sid in [s["skill_id"] for s in ctx.allowed_skills]:
            try:
                if execution_result == "success":
                    self.dispatcher.report_success(skill_id=sid, task_id=ctx.task_id,
                                                    session_id=ctx.session_id, duration=ctx.duration_seconds)
                else:
                    self.dispatcher.report_failure(skill_id=sid, failure_reason=execution_result,
                                                     risk_flag=(ctx.risk_level in ("high","critical")),
                                                     task_id=ctx.task_id, session_id=ctx.session_id,
                                                     duration=ctx.duration_seconds)
            except Exception as e:
                logger.warning("[Bridge] report failed for %s: %s", sid, e)

    def on_task_failure(self, ctx: BridgeTaskContext, failure_reason: str, risk_flag: bool = False) -> None:
        self.on_task_complete(ctx, execution_result=failure_reason)

    def _load_skill_card(self, skill_id: str) -> dict:
        try:
            from core.skill_registry import SkillRegistry
            return SkillRegistry(root=self.base_dir)._load_skill_card(skill_id) or {}
        except Exception: return {}

    def get_injected_context_for_hermes(self, task_description: str,
                                          task_type: Optional[str] = None,
                                          risk_level: str = "low") -> str:
        ctx = self.on_task_start(task_description=task_description, task_type=task_type, risk_level=risk_level)
        return ctx.to_hermes_system_context()