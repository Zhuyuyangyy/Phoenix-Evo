"""Collaboration protocol for multi-agent systems."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .agent_roles import AgentProfile, AgentRole
from .artifacts import Artifact, ArtifactType


class PipelineStage(Enum):
    """Stages in the collaboration pipeline."""
    PLANNING = "planning"
    IMPLEMENTATION = "implementation"
    REVIEW = "review"
    TESTING = "testing"
    INTEGRATION = "integration"


@dataclass
class PipelineStep:
    """A single step in the collaboration pipeline."""
    stage: PipelineStage
    assigned_agent: str
    input_artifacts: List[str] = field(default_factory=list)
    output_artifacts: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, in_progress, completed, failed
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CollaborationSession:
    """A collaboration session between multiple agents."""
    session_id: str
    task_description: str
    participants: List[AgentProfile]
    pipeline: List[PipelineStep]
    artifacts: Dict[str, Artifact] = field(default_factory=dict)
    status: str = "created"
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class CollaborationProtocol:
    """5-stage collaboration pipeline for multi-agent systems.

    Pipeline stages:
    1. Planning - Planner creates a plan
    2. Implementation - Coder implements the plan
    3. Review - Reviewer checks the implementation
    4. Testing - Tester validates the implementation
    5. Integration - Integrator merges and finalizes
    """

    STAGE_ROLE_MAPPING = {
        PipelineStage.PLANNING: AgentRole.PLANNER,
        PipelineStage.IMPLEMENTATION: AgentRole.CODER,
        PipelineStage.REVIEW: AgentRole.REVIEWER,
        PipelineStage.TESTING: AgentRole.TESTER,
        PipelineStage.INTEGRATION: AgentRole.INTEGRATOR,
    }

    def __init__(self):
        self._sessions: Dict[str, CollaborationSession] = {}

    def create_session(
        self,
        task_description: str,
        participants: List[AgentProfile],
    ) -> CollaborationSession:
        """Create a new collaboration session with a 5-stage pipeline."""
        session_id = str(uuid.uuid4())[:8]

        # Build pipeline based on available roles
        pipeline = []
        for stage in PipelineStage:
            required_role = self.STAGE_ROLE_MAPPING[stage]
            # Find an agent with the required role
            assigned = None
            for p in participants:
                if p.role == required_role:
                    assigned = p.agent_id
                    break
            if assigned is None:
                # Use coordinator as fallback
                for p in participants:
                    if p.role == AgentRole.COORDINATOR:
                        assigned = p.agent_id
                        break
            if assigned is None and participants:
                assigned = participants[0].agent_id

            pipeline.append(PipelineStep(
                stage=stage,
                assigned_agent=assigned or "unknown",
            ))

        session = CollaborationSession(
            session_id=session_id,
            task_description=task_description,
            participants=participants,
            pipeline=pipeline,
        )
        self._sessions[session_id] = session
        return session

    def advance_stage(self, session_id: str, artifact: Optional[Artifact] = None) -> Optional[PipelineStage]:
        """Advance a session to the next pipeline stage."""
        session = self._sessions.get(session_id)
        if not session:
            return None

        # Find current stage
        current_idx = None
        for i, step in enumerate(session.pipeline):
            if step.status in ("pending", "in_progress"):
                current_idx = i
                break

        if current_idx is None:
            return None

        # Complete current stage
        current_step = session.pipeline[current_idx]
        current_step.status = "completed"
        current_step.completed_at = time.time()

        if artifact:
            session.artifacts[artifact.artifact_id] = artifact
            current_step.output_artifacts.append(artifact.artifact_id)

        # Start next stage
        next_idx = current_idx + 1
        if next_idx < len(session.pipeline):
            next_step = session.pipeline[next_idx]
            next_step.status = "in_progress"
            next_step.started_at = time.time()
            next_step.input_artifacts = list(current_step.output_artifacts)
            return next_step.stage
        else:
            session.status = "completed"
            return None

    def get_session(self, session_id: str) -> Optional[CollaborationSession]:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions."""
        return [
            {
                "session_id": s.session_id,
                "task": s.task_description,
                "status": s.status,
                "n_participants": len(s.participants),
                "n_artifacts": len(s.artifacts),
            }
            for s in self._sessions.values()
        ]
