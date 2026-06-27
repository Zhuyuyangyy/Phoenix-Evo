"""
Tests for SkillEvidence module.
"""


from core.skill_evidence import SkillCard, SkillEvidenceManager


class TestSkillCard:
    """Test suite for SkillCard."""

    def test_default_values(self):
        """Test default SkillCard values."""
        card = SkillCard()
        assert card.skill_id == ""
        assert card.skill_name == ""
        assert card.status == "draft"
        assert card.risk_level == "low"
        assert card.quality_score == 0.0
        assert card.promotion_ready is False

    def test_to_dict(self):
        """Test converting card to dict."""
        card = SkillCard(skill_id="test", skill_name="test_skill")
        d = card.to_dict()
        assert d["skill_id"] == "test"
        assert d["skill_name"] == "test_skill"

    def test_from_dict(self):
        """Test creating card from dict."""
        d = {
            "skill_id": "test",
            "skill_name": "test_skill",
            "status": "active",
            "risk_level": "low",
        }
        card = SkillCard.from_dict(d)
        assert card.skill_id == "test"
        assert card.status == "active"

    def test_from_dict_filters_unknown_fields(self):
        """Test that from_dict filters unknown fields."""
        d = {
            "skill_id": "test",
            "unknown_field": "value",
        }
        card = SkillCard.from_dict(d)
        assert card.skill_id == "test"
        assert not hasattr(card, "unknown_field")


class TestSkillEvidenceManager:
    """Test suite for SkillEvidenceManager."""

    def test_init_creates_directory(self, tmp_path):
        """Test that initialization creates directory."""
        manager = SkillEvidenceManager(root=tmp_path)
        assert manager.cards_dir.exists()

    def test_create_card(self, tmp_path):
        """Test creating a skill card."""
        manager = SkillEvidenceManager(root=tmp_path)
        skill = {
            "skill_id": "test_001",
            "skill_name": "test_skill",
            "quality_score": 0.85,
            "procedure": ["step1", "step2", "step3"],
        }
        card = manager.create_card(skill, "traj_001")

        assert card.skill_id == "test_001"
        assert card.skill_name == "test_skill"
        assert card.status == "draft"
        assert "traj_001" in card.source_trajectory_ids

    def test_get_card(self, tmp_path):
        """Test getting a skill card."""
        manager = SkillEvidenceManager(root=tmp_path)
        skill = {"skill_id": "test_001", "skill_name": "test_skill"}
        manager.create_card(skill, "traj_001")

        card = manager.get_card("test_001")
        assert card is not None
        assert card.skill_id == "test_001"

    def test_get_card_nonexistent(self, tmp_path):
        """Test getting a non-existent card."""
        manager = SkillEvidenceManager(root=tmp_path)
        card = manager.get_card("nonexistent")
        assert card is None

    def test_save_card(self, tmp_path):
        """Test saving a card."""
        manager = SkillEvidenceManager(root=tmp_path)
        card = SkillCard(skill_id="test_001", skill_name="test_skill")
        manager.save_card(card)

        loaded = manager.get_card("test_001")
        assert loaded is not None
        assert loaded.skill_id == "test_001"

    def test_update_card(self, tmp_path):
        """Test updating a card."""
        manager = SkillEvidenceManager(root=tmp_path)
        skill = {"skill_id": "test_001", "skill_name": "test_skill"}
        manager.create_card(skill, "traj_001")

        updated = manager.update_card("test_001", status="verified", quality_score=0.95)
        assert updated is not None
        assert updated.status == "verified"
        assert updated.quality_score == 0.95

    def test_update_card_nonexistent(self, tmp_path):
        """Test updating a non-existent card."""
        manager = SkillEvidenceManager(root=tmp_path)
        result = manager.update_card("nonexistent", status="verified")
        assert result is None

    def test_list_cards(self, tmp_path):
        """Test listing all cards."""
        manager = SkillEvidenceManager(root=tmp_path)
        skill1 = {"skill_id": "test_001", "skill_name": "skill1"}
        skill2 = {"skill_id": "test_002", "skill_name": "skill2"}
        manager.create_card(skill1, "traj_001")
        manager.create_card(skill2, "traj_002")

        cards = manager.list_cards()
        assert len(cards) == 2

    def test_list_cards_filtered(self, tmp_path):
        """Test listing cards with status filter."""
        manager = SkillEvidenceManager(root=tmp_path)
        skill1 = {"skill_id": "test_001", "skill_name": "skill1"}
        skill2 = {"skill_id": "test_002", "skill_name": "skill2"}
        manager.create_card(skill1, "traj_001")
        manager.create_card(skill2, "traj_002")
        manager.update_card("test_001", status="verified")

        verified = manager.list_cards(status="verified")
        assert len(verified) == 1
        assert verified[0].skill_id == "test_001"

    def test_record_replay_result_pass(self, tmp_path):
        """Test recording a passing replay result."""
        manager = SkillEvidenceManager(root=tmp_path)
        skill = {"skill_id": "test_001", "skill_name": "test_skill"}
        manager.create_card(skill, "traj_001")

        card = manager.record_replay_result("test_001", "replay_001", True)
        assert card is not None
        assert card.replay_pass_count == 1
        assert card.replay_fail_count == 0
        assert "replay_001" in card.replay_report_ids

    def test_record_replay_result_fail(self, tmp_path):
        """Test recording a failing replay result."""
        manager = SkillEvidenceManager(root=tmp_path)
        skill = {"skill_id": "test_001", "skill_name": "test_skill"}
        manager.create_card(skill, "traj_001")

        card = manager.record_replay_result("test_001", "replay_001", False)
        assert card is not None
        assert card.replay_pass_count == 0
        assert card.replay_fail_count == 1

    def test_record_replay_result_nonexistent(self, tmp_path):
        """Test recording replay result for non-existent card."""
        manager = SkillEvidenceManager(root=tmp_path)
        result = manager.record_replay_result("nonexistent", "replay_001", True)
        assert result is None

    def test_set_promotion_ready(self, tmp_path):
        """Test setting promotion ready."""
        manager = SkillEvidenceManager(root=tmp_path)
        skill = {"skill_id": "test_001", "skill_name": "test_skill"}
        manager.create_card(skill, "traj_001")

        card = manager.set_promotion_ready("test_001", True, "passed all checks")
        assert card is not None
        assert card.promotion_ready is True
        assert card.promotion_note == "passed all checks"

    def test_get_pending_replay(self, tmp_path):
        """Test getting pending replay cards."""
        manager = SkillEvidenceManager(root=tmp_path)
        skill = {"skill_id": "test_001", "skill_name": "test_skill"}
        manager.create_card(skill, "traj_001")

        pending = manager.get_pending_replay()
        assert len(pending) == 1
        assert pending[0].skill_id == "test_001"

    def test_get_promotion_candidates(self, tmp_path):
        """Test getting promotion candidates."""
        manager = SkillEvidenceManager(root=tmp_path)
        skill = {"skill_id": "test_001", "skill_name": "test_skill"}
        manager.create_card(skill, "traj_001")
        manager.set_promotion_ready("test_001", True)
        manager.record_replay_result("test_001", "replay_001", True)

        candidates = manager.get_promotion_candidates()
        assert len(candidates) == 1

    def test_bind_trajectory(self, tmp_path):
        """Test binding additional trajectory."""
        manager = SkillEvidenceManager(root=tmp_path)
        skill = {"skill_id": "test_001", "skill_name": "test_skill"}
        manager.create_card(skill, "traj_001")

        card = manager.bind_trajectory("test_001", "traj_002")
        assert card is not None
        assert "traj_002" in card.source_trajectory_ids
        assert card.evidence_type == "merged"

    def test_bind_trajectory_duplicate(self, tmp_path):
        """Test binding duplicate trajectory."""
        manager = SkillEvidenceManager(root=tmp_path)
        skill = {"skill_id": "test_001", "skill_name": "test_skill"}
        manager.create_card(skill, "traj_001")

        card = manager.bind_trajectory("test_001", "traj_001")
        assert card is not None
        assert card.source_trajectory_ids.count("traj_001") == 1

    def test_card_path(self, tmp_path):
        """Test card path generation."""
        manager = SkillEvidenceManager(root=tmp_path)
        path = manager._card_path("test_001")
        assert path.name == "test_001.card.json"
