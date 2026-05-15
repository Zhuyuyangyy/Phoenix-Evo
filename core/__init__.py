"""
Phoenix-Evo 核心模块
V0.5 — Runtime Skill Router
"""

from .trajectory_logger import TrajectoryLogger
from .post_task_evaluator import PostTaskEvaluator, EvaluationResult
from .skill_miner import SkillMiner
from .skill_verifier import SkillVerifier, VerificationResult
from .skill_registry import SkillRegistry
from .immune_guard import ImmuneGuard, ImmuneDecision
from .immune_memory import ImmuneMemory, ImmuneRecord
from .quarantine_manager import QuarantineManager, QuarantineEntry
from .risk_policy import RiskProfile, RiskPolicy, IMMUNE_DECISION
# V0.3 Curator
from .skill_similarity import SkillVectorizer, SimilarityResult, SkillVector
from .drift_detector import DriftDetector, SkillHealthReport, DriftRecord
from .curator_policy import (
    CuratorPolicy,
    CuratorDecision,
    MergeAction,
    KeepAction,
    DowngradeAction,
    ArchiveAction,
    QuarantineAction,
    ReviewAction,
)
from .skill_curator import SkillCurator, CuratorScanReport, CuratorRunLog, CuratorLogger
# V0.4 Evidence & Replay
from .skill_evidence import SkillEvidenceManager, SkillCard
from .skill_benchmark import SkillBenchmark, BenchmarkCase
from .skill_replay import SkillReplay, ReplayReport, ReplayResult, EvidencePolicy
from .replay_reporter import ReplayReporter, EvidenceSummary
# V0.5 Runtime Skill Router
from .skill_retriever import SkillRetriever, SkillRetrievalResult, RetrievalMatch
from .skill_router import SkillRouter, RouterDecision, RouterResult
from .execution_guard import ExecutionGuard, ExecutionGateResult
from .fallback_manager import FallbackManager, FallbackAction
from .runtime_reporter import RuntimeReporter, RuntimeReport, SkillInvocation

# 主调度器
from .phoenix_evo import PhoenixEvo
