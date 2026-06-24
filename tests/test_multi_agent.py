"""Tests for multi-agent system."""


from core.multi_agent.agent_roles import AgentProfile, AgentRole
from core.multi_agent.artifacts import Artifact, ArtifactType
from core.multi_agent.collaboration_protocol import CollaborationProtocol, PipelineStage
from core.multi_agent.consensus import ConsensusMechanism, Vote
from core.multi_agent.orchestrator import MultiAgentOrchestrator, OrchestratorResult
from core.multi_agent.shared_memory import SafetyMemoryEntry, SharedSafetyMemory


class TestAgentRole:
    def test_all_roles(self):
        expected = ["PLANNER", "CODER", "REVIEWER", "TESTER",
                     "SECURITY_AUDITOR", "INTEGRATOR", "COORDINATOR", "OBSERVER"]
        for name in expected:
            assert hasattr(AgentRole, name)
        assert len(AgentRole) == 8


class TestAgentProfile:
    def test_create(self):
        profile = AgentProfile(agent_id="a1", role=AgentRole.CODER, name="Coder1")
        assert profile.role == AgentRole.CODER
        assert profile.trust_score == 1.0

    def test_can_perform(self):
        profile = AgentProfile(
            agent_id="a1", role=AgentRole.CODER,
            capabilities=["python", "shell"],
        )
        assert profile.can_perform("python")
        assert not profile.can_perform("rust")

    def test_is_available(self):
        profile = AgentProfile(agent_id="a1", role=AgentRole.CODER, max_concurrent_tasks=3)
        assert profile.is_available(0)
        assert profile.is_available(2)
        assert not profile.is_available(3)

    def test_to_dict(self):
        profile = AgentProfile(agent_id="a1", role=AgentRole.CODER)
        d = profile.to_dict()
        assert d["role"] == "coder"

    def test_from_dict(self):
        d = {"agent_id": "a1", "role": "coder", "name": "Test"}
        profile = AgentProfile.from_dict(d)
        assert profile.role == AgentRole.CODER


class TestArtifact:
    def test_create(self):
        art = Artifact(
            artifact_id="art1",
            artifact_type=ArtifactType.CODE,
            producer_id="a1",
            content="print('hello')",
        )
        assert art.artifact_type == ArtifactType.CODE

    def test_content_hash(self):
        art = Artifact(
            artifact_id="art1", artifact_type=ArtifactType.CODE,
            producer_id="a1", content="test",
        )
        h = art.content_hash()
        assert len(h) == 16

    def test_artifact_types(self):
        types = ["CODE", "DOCUMENTATION", "TEST_RESULT", "REVIEW_COMMENT",
                  "SECURITY_REPORT", "PLAN"]
        for t in types:
            assert hasattr(ArtifactType, t)
        assert len(ArtifactType) == 6


class TestCollaborationProtocol:
    def test_create_session(self):
        protocol = CollaborationProtocol()
        participants = [
            AgentProfile(agent_id="p1", role=AgentRole.PLANNER),
            AgentProfile(agent_id="c1", role=AgentRole.CODER),
        ]
        session = protocol.create_session("Build a feature", participants)
        assert session is not None
        assert len(session.pipeline) == 5  # 5 stages

    def test_advance_stage(self):
        protocol = CollaborationProtocol()
        participants = [AgentProfile(agent_id="p1", role=AgentRole.PLANNER)]
        session = protocol.create_session("Test task", participants)
        next_stage = protocol.advance_stage(session.session_id)
        assert next_stage is not None or session.pipeline[0].status == "completed"

    def test_pipeline_stages(self):
        assert len(PipelineStage) == 5


class TestConsensusMechanism:
    def test_vote_majority(self):
        cm = ConsensusMechanism()
        votes = [
            Vote(voter_id="v1", choice=True),
            Vote(voter_id="v2", choice=True),
            Vote(voter_id="v3", choice=False),
        ]
        result = cm.vote("p1", votes)
        assert result.passed is True
        assert result.outcome is True

    def test_vote_no_majority(self):
        cm = ConsensusMechanism(vote_threshold=0.67)
        votes = [
            Vote(voter_id="v1", choice=True),
            Vote(voter_id="v2", choice=False),
            Vote(voter_id="v3", choice=False),
        ]
        result = cm.vote("p1", votes)
        assert result.passed is False

    def test_review(self):
        cm = ConsensusMechanism(review_required_approvals=2)
        reviews = [
            Vote(voter_id="r1", choice="approve"),
            Vote(voter_id="r2", choice="approve"),
        ]
        result = cm.review("p1", reviews)
        assert result.passed is True

    def test_review_with_rejection(self):
        cm = ConsensusMechanism()
        reviews = [
            Vote(voter_id="r1", choice="approve"),
            Vote(voter_id="r2", choice="reject"),
        ]
        result = cm.review("p1", reviews)
        assert result.passed is False

    def test_challenge(self):
        cm = ConsensusMechanism()
        proposer = Vote(voter_id="p1", choice=True)
        challengers = [
            Vote(voter_id="c1", choice="challenge"),
        ]
        result = cm.challenge("p1", proposer, challengers)
        assert result.passed is False

    def test_challenge_upheld(self):
        cm = ConsensusMechanism()
        proposer = Vote(voter_id="p1", choice=True)
        challengers = [
            Vote(voter_id="c1", choice="approve"),
        ]
        result = cm.challenge("p1", proposer, challengers)
        assert result.passed is True

    def test_empty_votes(self):
        cm = ConsensusMechanism()
        result = cm.vote("p1", [])
        assert result.passed is False


class TestSharedSafetyMemory:
    def test_store_and_retrieve(self):
        mem = SharedSafetyMemory()
        entry = SafetyMemoryEntry(
            entry_id="e1", category="violation",
            description="test", reporter_id="a1",
        )
        mem.store(entry)
        assert mem.retrieve("e1") is not None

    def test_query_by_category(self):
        mem = SharedSafetyMemory()
        mem.store(SafetyMemoryEntry(entry_id="e1", category="violation", description="t1", reporter_id="a1"))
        mem.store(SafetyMemoryEntry(entry_id="e2", category="near_miss", description="t2", reporter_id="a1"))
        violations = mem.query_by_category("violation")
        assert len(violations) == 1

    def test_query_by_severity(self):
        mem = SharedSafetyMemory()
        mem.store(SafetyMemoryEntry(entry_id="e1", category="v", description="t", reporter_id="a1", severity=0.9))
        mem.store(SafetyMemoryEntry(entry_id="e2", category="v", description="t", reporter_id="a1", severity=0.3))
        high = mem.query_by_severity(min_severity=0.8)
        assert len(high) == 1

    def test_get_violations(self):
        mem = SharedSafetyMemory()
        mem.store(SafetyMemoryEntry(entry_id="e1", category="violation", description="t", reporter_id="a1"))
        assert len(mem.get_violations()) == 1

    def test_summary(self):
        mem = SharedSafetyMemory()
        mem.store(SafetyMemoryEntry(entry_id="e1", category="violation", description="t", reporter_id="a1", tags=["security"]))
        summary = mem.summary()
        assert summary["total_entries"] == 1


class TestMultiAgentOrchestrator:
    def test_register_agent(self):
        orch = MultiAgentOrchestrator()
        orch.register_agent(AgentProfile(agent_id="a1", role=AgentRole.CODER))
        assert orch.get_agent("a1") is not None

    def test_list_agents(self):
        orch = MultiAgentOrchestrator()
        orch.register_agent(AgentProfile(agent_id="a1", role=AgentRole.CODER))
        orch.register_agent(AgentProfile(agent_id="a2", role=AgentRole.PLANNER))
        assert len(orch.list_agents()) == 2
        assert len(orch.list_agents(AgentRole.CODER)) == 1

    def test_execute_task(self):
        orch = MultiAgentOrchestrator()
        orch.register_agent(AgentProfile(agent_id="a1", role=AgentRole.PLANNER))
        orch.register_agent(AgentProfile(agent_id="a2", role=AgentRole.CODER))
        result = orch.execute_task("Build feature")
        assert isinstance(result, OrchestratorResult)

    def test_execute_task_no_agents(self):
        orch = MultiAgentOrchestrator()
        result = orch.execute_task("Build feature")
        assert result.success is False
        assert result.error == "No agents available"

    def test_report_safety_event(self):
        orch = MultiAgentOrchestrator()
        entry = orch.report_safety_event(
            category="violation",
            description="test violation",
            reporter_id="a1",
        )
        assert entry.entry_id is not None

    def test_unregister_agent(self):
        orch = MultiAgentOrchestrator()
        orch.register_agent(AgentProfile(agent_id="a1", role=AgentRole.CODER))
        orch.unregister_agent("a1")
        assert orch.get_agent("a1") is None
