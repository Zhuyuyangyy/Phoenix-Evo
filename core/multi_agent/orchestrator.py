"""Multi-agent orchestrator for Phoenix-Evo."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .agent_roles import AgentProfile, AgentRole
from .artifacts import Artifact, ArtifactType
from .collaboration_protocol import CollaborationProtocol, CollaborationSession
from .consensus import ConsensusMechanism, ConsensusMethod, Vote
from .shared_memory import SafetyMemoryEntry, SharedSafetyMemory


@dataclass
class OrchestratorResult:
    """Result from the multi-agent orchestrator."""
    task_id: str
    success: bool
    session: Optional[CollaborationSession] = None
    artifacts: List[Artifact] = field(default_factory=list)
    safety_events: List[SafetyMemoryEntry] = field(default_factory=list)
    duration_seconds: float = 0.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class MultiAgentOrchestrator:
    """Orchestrates multi-agent collaboration for complex tasks.

    Coordinates agents through the 5-stage collaboration pipeline,
    manages consensus, and maintains shared safety memory.
    """

    def __init__(
        self,
        protocol: Optional[CollaborationProtocol] = None,
        consensus: Optional[ConsensusMechanism] = None,
        safety_memory: Optional[SharedSafetyMemory] = None,
    ):
        self.protocol = protocol or CollaborationProtocol()
        self.consensus = consensus or ConsensusMechanism()
        self.safety_memory = safety_memory or SharedSafetyMemory()
        self._agents: Dict[str, AgentProfile] = {}
        self._results: List[OrchestratorResult] = []

    def register_agent(self, profile: AgentProfile) -> None:
        """Register an agent with the orchestrator."""
        self._agents[profile.agent_id] = profile

    def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent."""
        self._agents.pop(agent_id, None)

    def get_agent(self, agent_id: str) -> Optional[AgentProfile]:
        """Get an agent profile."""
        return self._agents.get(agent_id)

    def list_agents(self, role: Optional[AgentRole] = None) -> List[AgentProfile]:
        """List registered agents, optionally filtered by role."""
        agents = list(self._agents.values())
        if role:
            agents = [a for a in agents if a.role == role]
        return agents

    def execute_task(
        self,
        task_description: str,
        required_roles: Optional[List[AgentRole]] = None,
        executor: Optional[Callable] = None,
    ) -> OrchestratorResult:
        """Execute a task using multi-agent collaboration."""
        start_time = time.time()
        task_id = str(uuid.uuid4())[:8]

        # Select participants
        if required_roles:
            participants = []
            for role in required_roles:
                agents_with_role = self.list_agents(role)
                if agents_with_role:
                    participants.append(agents_with_role[0])
        else:
            participants = list(self._agents.values())

        if not participants:
            return OrchestratorResult(
                task_id=task_id,
                success=False,
                error="No agents available",
                duration_seconds=time.time() - start_time,
            )

        # Create collaboration session
        session = self.protocol.create_session(task_description, participants)

        # Simulate pipeline execution
        artifacts = []
        for step in session.pipeline:
            step.status = "in_progress"
            step.started_at = time.time()

            if executor:
                try:
                    result = executor(step, session)
                    if isinstance(result, Artifact):
                        artifacts.append(result)
                        session.artifacts[result.artifact_id] = result
                except Exception as e:
                    step.status = "failed"
                    step.metadata["error"] = str(e)
                    break

            step.status = "completed"
            step.completed_at = time.time()

            # Advance to next stage
            next_stage = self.protocol.advance_stage(
                session.session_id,
                artifact=artifacts[-1] if artifacts else None,
            )

        success = all(s.status == "completed" for s in session.pipeline)
        session.status = "completed" if success else "partial"

        result = OrchestratorResult(
            task_id=task_id,
            success=success,
            session=session,
            artifacts=artifacts,
            duration_seconds=time.time() - start_time,
        )
        self._results.append(result)
        return result

    def request_consensus(
        self,
        proposal_id: str,
        proposal: Any,
        method: ConsensusMethod = ConsensusMethod.VOTE,
    ) -> Any:
        """Request consensus from agents on a proposal."""
        votes = []
        for agent in self._agents.values():
            # Simple voting: agents with higher trust have more weight
            vote = Vote(
                voter_id=agent.agent_id,
                choice=True,
                confidence=agent.trust_score,
            )
            votes.append(vote)

        if method == ConsensusMethod.VOTE:
            return self.consensus.vote(proposal_id, votes)
        elif method == ConsensusMethod.REVIEW:
            return self.consensus.review(proposal_id, votes)
        elif method == ConsensusMethod.CHALLENGE:
            if votes:
                return self.consensus.challenge(proposal_id, votes[0], votes[1:])
            return None

    def report_safety_event(
        self,
        category: str,
        description: str,
        reporter_id: str,
        severity: float = 0.5,
        tags: Optional[List[str]] = None,
    ) -> SafetyMemoryEntry:
        """Report a safety event to shared memory."""
        entry = SafetyMemoryEntry(
            entry_id=str(uuid.uuid4())[:8],
            category=category,
            description=description,
            reporter_id=reporter_id,
            severity=severity,
            tags=tags or [],
        )
        self.safety_memory.store(entry)
        return entry

    def get_results(self) -> List[OrchestratorResult]:
        """Get all orchestrator results."""
        return list(self._results)
