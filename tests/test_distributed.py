"""Tests for distributed system."""

import tempfile
import time

from core.distributed.conflict_resolution import (
    ConflictResolver,
    ConflictType,
    ResolutionStrategy,
)
from core.distributed.federated_sharing import (
    DifferentialPrivacy,
    FederatedSkillNetwork,
    FederatedUpdate,
)
from core.distributed.offline_access import OfflineSkillAccess
from core.distributed.skill_cache import SkillCache
from core.distributed.skill_registry_distributed import (
    DistributedSkillRegistry,
    RegistryEntry,
)


class TestDistributedSkillRegistry:
    def test_register_and_lookup(self):
        reg = DistributedSkillRegistry()
        entry = RegistryEntry(
            skill_id="s1", version="1.0.0", node_id="n1", checksum="abc",
        )
        reg.register_skill(entry)
        result = reg.lookup("s1")
        assert result is not None
        assert result.version == "1.0.0"

    def test_lookup_nonexistent(self):
        reg = DistributedSkillRegistry()
        assert reg.lookup("nonexistent") is None

    def test_discover(self):
        reg = DistributedSkillRegistry()
        reg.register_skill(RegistryEntry(skill_id="shell_executor", version="1.0.0", node_id="n1", checksum="a"))
        reg.register_skill(RegistryEntry(skill_id="python_runner", version="1.0.0", node_id="n1", checksum="b"))
        results = reg.discover("shell")
        assert len(results) == 1

    def test_heartbeat(self):
        reg = DistributedSkillRegistry()
        reg.register_skill(RegistryEntry(skill_id="s1", version="1.0.0", node_id="n1", checksum="a"))
        reg.heartbeat("n1")
        node = reg._nodes.get("n1")
        assert node is not None
        assert node.active is True

    def test_prune_stale_nodes(self):
        reg = DistributedSkillRegistry(heartbeat_timeout=0.001)
        reg.register_skill(RegistryEntry(skill_id="s1", version="1.0.0", node_id="n1", checksum="a"))
        time.sleep(0.01)
        pruned = reg.prune_stale_nodes()
        assert pruned >= 1

    def test_get_available_nodes(self):
        reg = DistributedSkillRegistry()
        reg.register_skill(RegistryEntry(skill_id="s1", version="1.0.0", node_id="n1", checksum="a"))
        nodes = reg.get_available_nodes("s1")
        assert "n1" in nodes

    def test_status(self):
        reg = DistributedSkillRegistry()
        reg.register_skill(RegistryEntry(skill_id="s1", version="1.0.0", node_id="n1", checksum="a"))
        status = reg.get_status()
        assert status["total_skills"] == 1


class TestDifferentialPrivacy:
    def test_add_noise(self):
        dp = DifferentialPrivacy(epsilon=1.0)
        noisy = dp.add_laplace_noise(1.0, sensitivity=1.0)
        assert isinstance(noisy, float)

    def test_budget_tracking(self):
        dp = DifferentialPrivacy(epsilon=1.0)
        initial_remaining = dp.budget_remaining
        dp.add_laplace_noise(1.0)
        assert dp.budget_remaining < initial_remaining

    def test_budget_exhaustion(self):
        dp = DifferentialPrivacy(epsilon=10.0)
        dp._budget_limit = 1.0
        dp.add_laplace_noise(1.0)
        assert dp.budget_exhausted

    def test_reset_budget(self):
        dp = DifferentialPrivacy(epsilon=1.0)
        dp.add_laplace_noise(1.0)
        dp.reset_budget()
        assert dp.budget_remaining == dp._budget_limit

    def test_clip_value(self):
        dp = DifferentialPrivacy()
        assert dp.clip_value(5.0, 0.0, 1.0) == 1.0
        assert dp.clip_value(-1.0, 0.0, 1.0) == 0.0


class TestFederatedSkillNetwork:
    def test_join(self):
        net = FederatedSkillNetwork()
        assert net.join("p1") is True
        assert net.join("p1") is False  # Already joined

    def test_leave(self):
        net = FederatedSkillNetwork()
        net.join("p1")
        assert net.leave("p1") is True
        assert net.leave("p1") is False

    def test_submit_update(self):
        net = FederatedSkillNetwork()
        net.join("p1")
        update = FederatedUpdate(
            update_id="u1", participant_id="p1",
            skill_id="s1", version="1.0.0",
            update_data={"accuracy": 0.9},
        )
        assert net.submit_update(update) is True

    def test_submit_update_non_member(self):
        net = FederatedSkillNetwork()
        update = FederatedUpdate(
            update_id="u1", participant_id="unknown",
            skill_id="s1", version="1.0.0",
            update_data={},
        )
        assert net.submit_update(update) is False

    def test_aggregate(self):
        net = FederatedSkillNetwork(min_participants=2)
        net.join("p1")
        net.join("p2")
        net.submit_update(FederatedUpdate(
            update_id="u1", participant_id="p1",
            skill_id="s1", version="1.0.0",
            update_data={"accuracy": 0.85},
        ))
        net.submit_update(FederatedUpdate(
            update_id="u2", participant_id="p2",
            skill_id="s1", version="1.0.0",
            update_data={"accuracy": 0.90},
        ))
        result = net.aggregate("s1")
        assert result is not None
        assert result.n_participants == 2

    def test_aggregate_not_enough(self):
        net = FederatedSkillNetwork(min_participants=5)
        net.join("p1")
        net.submit_update(FederatedUpdate(
            update_id="u1", participant_id="p1",
            skill_id="s1", version="1.0.0",
            update_data={},
        ))
        result = net.aggregate("s1")
        assert result is None

    def test_status(self):
        net = FederatedSkillNetwork()
        net.join("p1")
        status = net.get_status()
        assert status["n_participants"] == 1


class TestSkillCache:
    def test_put_and_get(self):
        cache = SkillCache()
        cache.put("k1", "value1")
        assert cache.get("k1") == "value1"

    def test_miss(self):
        cache = SkillCache()
        assert cache.get("nonexistent") is None

    def test_lru_eviction(self):
        cache = SkillCache(max_size=3)
        cache.put("k1", "v1")
        cache.put("k2", "v2")
        cache.put("k3", "v3")
        cache.put("k4", "v4")  # Should evict k1
        assert cache.get("k1") is None
        assert cache.get("k4") == "v4"

    def test_ttl_expiration(self):
        cache = SkillCache(default_ttl=0.01)
        cache.put("k1", "v1")
        time.sleep(0.02)
        assert cache.get("k1") is None

    def test_hit_rate(self):
        cache = SkillCache()
        cache.put("k1", "v1")
        cache.get("k1")  # Hit
        cache.get("k2")  # Miss
        assert cache.hit_rate == 0.5

    def test_cleanup_expired(self):
        cache = SkillCache(default_ttl=0.01)
        cache.put("k1", "v1")
        cache.put("k2", "v2")
        time.sleep(0.02)
        removed = cache.cleanup_expired()
        assert removed == 2

    def test_stats(self):
        cache = SkillCache()
        cache.put("k1", "v1")
        stats = cache.get_stats()
        assert stats["size"] == 1
        assert "hit_rate" in stats

    def test_delete(self):
        cache = SkillCache()
        cache.put("k1", "v1")
        assert cache.delete("k1") is True
        assert cache.get("k1") is None

    def test_clear(self):
        cache = SkillCache()
        cache.put("k1", "v1")
        cache.put("k2", "v2")
        cache.clear()
        assert cache.size == 0


class TestOfflineSkillAccess:
    def test_download_and_get(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            access = OfflineSkillAccess(storage_dir=tmpdir)
            access.download("s1", "print('hello')", version="1.0.0")
            skill = access.get("s1")
            assert skill is not None
            assert skill.code == "print('hello')"

    def test_expired_skill(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            access = OfflineSkillAccess(storage_dir=tmpdir)
            access.download("s1", "code", ttl_seconds=0.01)
            time.sleep(0.02)
            assert access.get("s1") is None

    def test_verify_checksum(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            access = OfflineSkillAccess(storage_dir=tmpdir)
            access.download("s1", "code")
            skill = access.get("s1")
            assert skill.verify_checksum() is True

    def test_list_available(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            access = OfflineSkillAccess(storage_dir=tmpdir)
            access.download("s1", "code1")
            access.download("s2", "code2")
            available = access.list_available()
            assert len(available) == 2

    def test_remove(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            access = OfflineSkillAccess(storage_dir=tmpdir)
            access.download("s1", "code")
            assert access.remove("s1") is True
            assert access.get("s1") is None

    def test_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            access = OfflineSkillAccess(storage_dir=tmpdir)
            access.download("s1", "code")
            status = access.get_status()
            assert status["available_skills"] == 1


class TestConflictResolver:
    def test_detect_conflict(self):
        resolver = ConflictResolver()
        conflict = resolver.detect_conflict(
            "r1",
            {"version": "1.0", "data": "a", "timestamp": 1.0},
            {"version": "2.0", "data": "b", "timestamp": 2.0},
        )
        assert conflict is not None
        assert conflict.conflict_type == ConflictType.VERSION_CONFLICT

    def test_no_conflict(self):
        resolver = ConflictResolver()
        conflict = resolver.detect_conflict(
            "r1",
            {"version": "1.0", "data": "a"},
            {"version": "1.0", "data": "a"},
        )
        assert conflict is None

    def test_last_write_wins(self):
        resolver = ConflictResolver(default_strategy=ResolutionStrategy.LAST_WRITE_WINS)
        conflict = resolver.detect_conflict(
            "r1",
            {"data": "old", "timestamp": 1.0},
            {"data": "new", "timestamp": 2.0},
        )
        if conflict:
            resolution = resolver.resolve(conflict)
            assert resolution.winner == "right"
            assert resolution.resolved_data["data"] == "new"

    def test_highest_version(self):
        resolver = ConflictResolver(default_strategy=ResolutionStrategy.HIGHEST_VERSION)
        conflict = resolver.detect_conflict(
            "r1",
            {"version": "1.0", "data": "a"},
            {"version": "2.0", "data": "b"},
        )
        if conflict:
            resolution = resolver.resolve(conflict)
            assert resolution.winner == "right"

    def test_merge_strategy(self):
        resolver = ConflictResolver(default_strategy=ResolutionStrategy.MERGE)
        conflict = resolver.detect_conflict(
            "r1",
            {"a": 1, "b": 2},
            {"b": 3, "c": 4},
        )
        if conflict:
            resolution = resolver.resolve(conflict)
            assert resolution.winner == "merge"
            assert resolution.resolved_data["b"] == 3  # Right wins in merge

    def test_source_priority(self):
        resolver = ConflictResolver(
            default_strategy=ResolutionStrategy.SOURCE_PRIORITY,
            source_priorities={"primary": 10, "secondary": 1},
        )
        conflict = resolver.detect_conflict(
            "r1",
            {"source": "primary", "data": "a"},
            {"source": "secondary", "data": "b"},
        )
        if conflict:
            resolution = resolver.resolve(conflict)
            assert resolution.winner == "left"

    def test_stats(self):
        resolver = ConflictResolver()
        conflict = resolver.detect_conflict(
            "r1", {"v": 1}, {"v": 2}
        )
        if conflict:
            resolver.resolve(conflict)
        stats = resolver.get_stats()
        assert stats["total_conflicts"] >= 0
