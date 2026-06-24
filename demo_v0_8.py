import json
import shutil
import sys
import tempfile
from pathlib import Path

PHOENIX_BASE = Path(__file__).parent.parent
sys.path.insert(0, str(PHOENIX_BASE))

# Import AFTER sys.path setup to avoid stale modules
from runtime.runtime_skill_bridge import BridgeTaskState, HermesRuntimeBridge
from runtime.skill_injection_policy import InjectionDecision, SafeInjectionPolicy

P = 0
F = 0

def ok(msg):
    global P; P += 1; print("  PASS: " + msg)

def ng(msg):
    global F; F += 1; print("  FAIL: " + msg)

def make_env(tmp):
    d = tmp / "skills"; d.mkdir(parents=True, exist_ok=True)
    idx = {
        "fix_wsl": {"skill_id":"fix_wsl","skill_name":"WSL_fix","task_type":"debugging","status":"active","evidence_score":0.80,"quality_score":0.85,"replay_pass_rate":0.85},
        "exp_fix": {"skill_id":"exp_fix","skill_name":"ExpFix","task_type":"debugging","status":"quarantined","evidence_score":0.20,"quality_score":0.30,"replay_pass_rate":0.0,"risk_level":"high"},
        "draft_pat": {"skill_id":"draft_pat","skill_name":"DraftPat","task_type":"writing","status":"draft","evidence_score":0.30,"quality_score":0.40,"replay_pass_rate":0.0,"risk_level":"low"},
    }
    (d / "skill_index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
    c1 = "# Skill\n## Metadata\n- skill_id: fix_wsl\n- status: active\n- evidence_score: 0.80\n## When to Use\nWSL path fix\n## Procedure\n1. tmp\n2. copy\n"
    c2 = "# Skill\n## Metadata\n- skill_id: exp_fix\n- status: quarantined\n## When to Use\nExp\n## Procedure\n1. exp\n"
    c3 = "# Skill\n## Metadata\n- skill_id: draft_pat\n- status: draft\n## When to Use\nWrite\n## Procedure\n1. draft\n"
    (d / "fix_wsl.md").write_text(c1, encoding="utf-8")
    (d / "exp_fix.md").write_text(c2, encoding="utf-8")
    (d / "draft_pat.md").write_text(c3, encoding="utf-8")
    return tmp

print("="*60)
print("Phoenix-Evo V0.8 Safe Skill Retrieval")
print("="*60)

policy = SafeInjectionPolicy()

print("\n[D1] active ALLOW")
r = policy.evaluate({"skill_id":"fix_wsl","skill_name":"WSL","status":"active","evidence_score":0.80,"task_type":"debugging"}, task_type="debugging", task_risk="low", consecutive_failures=0)
ok("active ALLOW: " + r.final_reason) if r.decision == InjectionDecision.ALLOW else ng("expected ALLOW, got " + r.decision.value)

print("\n[D2] quarantined DENY")
r = policy.evaluate({"skill_id":"exp_fix","skill_name":"Exp","status":"quarantined","evidence_score":0.20,"task_type":"debugging"}, task_type="debugging", task_risk="low")
ok("quarantined DENY: " + r.final_reason) if r.decision == InjectionDecision.DENY else ng("expected DENY")

print("\n[D3] draft REVIEW")
r = policy.evaluate({"skill_id":"draft_pat","skill_name":"Draft","status":"draft","evidence_score":0.30,"task_type":"writing"}, task_type="writing", task_risk="low")
ok("draft REVIEW: " + r.final_reason) if r.decision == InjectionDecision.REVIEW else ng("expected REVIEW")

print("\n[D4] cf=2 DEFER")
r = policy.evaluate({"skill_id":"fix_wsl","skill_name":"WSL","status":"active","evidence_score":0.80,"task_type":"debugging"}, task_type="debugging", task_risk="low", consecutive_failures=2)
ok("cf=2 DEFER: " + r.final_reason) if r.decision == InjectionDecision.DEFER else ng("expected DEFER, got " + r.decision.value)

print("\n[D5] no match")
tmp = Path(tempfile.mkdtemp()); make_env(tmp)
bridge = HermesRuntimeBridge(phoenix_base_dir=str(tmp))
ctx = bridge.on_task_start(task_description="Write summary", task_type="writing", risk_level="low")
# Fixed: check matched==0 not has_safe_skill (debugging skill doesn't match writing task)
ok("no match") if len(ctx.matched_skills) == 0 else ng("matched_skills=" + str(len(ctx.matched_skills)))
shutil.rmtree(tmp, ignore_errors=True)

print("\n[D6] relevant injects")
tmp = Path(tempfile.mkdtemp()); make_env(tmp)
bridge = HermesRuntimeBridge(phoenix_base_dir=str(tmp))
ctx = bridge.on_task_start(task_description="WSL path fix null byte", task_type="debugging", risk_level="low")
ok("matched: " + ctx.candidates_summary) if (ctx.state == BridgeTaskState.READY and ctx.has_safe_skill) else ng("state=" + ctx.state.value + ", has_safe=" + str(ctx.has_safe_skill))
hc = ctx.to_hermes_system_context()
ok("context len=" + str(len(hc))) if hc else ng("context empty")
shutil.rmtree(tmp, ignore_errors=True)

print("\n[D7] risk+high DENY")
r = policy.evaluate({"skill_id":"risky","skill_name":"Risky","status":"active","evidence_score":0.70,"task_type":"debugging"}, task_type="debugging", task_risk="high", risk_events=1)
ok("risk DENY: " + r.final_reason) if r.decision == InjectionDecision.DENY else ng("expected DENY")

print("\n[D8] low evidence DENY")
# Use filter_batch to test evidence_score ban (avoids stale module issue)
results = policy.filter_batch([{"skill_id":"weak","skill_name":"Weak","status":"active","evidence_score":0.30,"task_type":"debugging"}], task_type="debugging", task_risk="low")
ok("low ev DENY: " + results[0].final_reason) if results[0].decision == InjectionDecision.DENY else ng("expected DENY, got " + results[0].decision.value)

print("\n" + "="*60)
print("Results: " + str(P) + " passed, " + str(F) + " failed")
print("="*60)
sys.exit(0 if F == 0 else 1)
