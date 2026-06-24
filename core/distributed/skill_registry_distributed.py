"""Distributed skill registry for Phoenix-Evo."""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class RegistryEntry:
    """An entry in the distributed skill registry."""
    skill_id: str
    version: str
    node_id: str
    checksum: str
    registered_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RegistryNode:
    """A node in the distributed registry."""
    node_id: str
    address: str
    last_seen: float = field(default_factory=time.time)
    skills: Set[str] = field(default_factory=set)
    active: bool = True


class DistributedSkillRegistry:
    """Distributed registry for skill discovery and lookup.

    Maintains a registry of skills across multiple nodes,
    with heartbeat-based health checking and conflict resolution.
    """

    def __init__(self, node_id: Optional[str] = None, heartbeat_timeout: float = 300.0):
        self.node_id = node_id or f"node_{uuid.uuid4().hex[:8]}"
        self.heartbeat_timeout = heartbeat_timeout
        self._entries: Dict[str, RegistryEntry] = {}  # skill_id -> entry
        self._nodes: Dict[str, RegistryNode] = {}  # node_id -> node
        self._skill_nodes: Dict[str, Set[str]] = {}  # skill_id -> set of node_ids

    def register_skill(self, entry: RegistryEntry) -> None:
        """Register a skill in the distributed registry."""
        self._entries[entry.skill_id] = entry

        # Track which node has this skill
        if entry.skill_id not in self._skill_nodes:
            self._skill_nodes[entry.skill_id] = set()
        self._skill_nodes[entry.skill_id].add(entry.node_id)

        # Register the node
        if entry.node_id not in self._nodes:
            self._nodes[entry.node_id] = RegistryNode(
                node_id=entry.node_id,
                address="",
            )
        self._nodes[entry.node_id].skills.add(entry.skill_id)
        self._nodes[entry.node_id].last_seen = time.time()

    def lookup(self, skill_id: str) -> Optional[RegistryEntry]:
        """Look up a skill by ID."""
        return self._entries.get(skill_id)

    def lookup_by_node(self, node_id: str) -> List[RegistryEntry]:
        """Look up all skills on a specific node."""
        node = self._nodes.get(node_id)
        if not node:
            return []
        return [self._entries[sid] for sid in node.skills if sid in self._entries]

    def discover(self, query: str) -> List[RegistryEntry]:
        """Discover skills matching a query."""
        results = []
        query_lower = query.lower()
        for entry in self._entries.values():
            if query_lower in entry.skill_id.lower() or query_lower in str(entry.metadata).lower():
                results.append(entry)
        return results

    def heartbeat(self, node_id: str) -> None:
        """Process a heartbeat from a node."""
        node = self._nodes.get(node_id)
        if node:
            node.last_seen = time.time()
            node.active = True

    def prune_stale_nodes(self) -> int:
        """Remove nodes that haven't sent heartbeats. Returns count of pruned nodes."""
        now = time.time()
        pruned = 0
        for node_id, node in list(self._nodes.items()):
            if now - node.last_seen > self.heartbeat_timeout:
                node.active = False
                # Remove skills from this node
                for skill_id in list(node.skills):
                    if skill_id in self._skill_nodes:
                        self._skill_nodes[skill_id].discard(node_id)
                pruned += 1
        return pruned

    def get_available_nodes(self, skill_id: str) -> List[str]:
        """Get list of active nodes that have a specific skill."""
        node_ids = self._skill_nodes.get(skill_id, set())
        return [
            nid for nid in node_ids
            if nid in self._nodes and self._nodes[nid].active
        ]

    def get_status(self) -> Dict[str, Any]:
        """Get the status of the distributed registry."""
        active_nodes = sum(1 for n in self._nodes.values() if n.active)
        return {
            "node_id": self.node_id,
            "total_skills": len(self._entries),
            "total_nodes": len(self._nodes),
            "active_nodes": active_nodes,
            "stale_nodes": len(self._nodes) - active_nodes,
        }
