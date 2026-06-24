"""Skill cache with LRU and TTL for Phoenix-Evo distributed system."""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CacheEntry:
    """An entry in the skill cache."""
    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    ttl_seconds: Optional[float] = None
    access_count: int = 0
    size_bytes: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        """Check if the entry has expired."""
        if self.ttl_seconds is None:
            return False
        return time.time() - self.created_at > self.ttl_seconds


class SkillCache:
    """LRU + TTL skill cache for distributed skill access.

    Provides fast local access to frequently used skills with
    automatic eviction based on LRU policy and TTL expiration.
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: Optional[float] = 3600.0,
        max_memory_bytes: int = 100 * 1024 * 1024,  # 100 MB
    ):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.max_memory_bytes = max_memory_bytes
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._current_memory: int = 0
        self._hits: int = 0
        self._misses: int = 0
        self._evictions: int = 0

    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache. Returns None if not found or expired."""
        entry = self._cache.get(key)

        if entry is None:
            self._misses += 1
            return None

        if entry.is_expired:
            self._remove(key)
            self._misses += 1
            return None

        # Update access info (LRU)
        entry.last_accessed = time.time()
        entry.access_count += 1
        self._cache.move_to_end(key)
        self._hits += 1
        return entry.value

    def put(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
        size_bytes: int = 0,
    ) -> None:
        """Put a value into the cache."""
        # Remove existing entry if present
        if key in self._cache:
            self._remove(key)

        # Evict if at capacity
        while len(self._cache) >= self.max_size:
            self._evict_lru()

        # Evict if memory limit exceeded
        while self._current_memory + size_bytes > self.max_memory_bytes and self._cache:
            self._evict_lru()

        entry = CacheEntry(
            key=key,
            value=value,
            ttl_seconds=ttl if ttl is not None else self.default_ttl,
            size_bytes=size_bytes,
        )
        self._cache[key] = entry
        self._current_memory += size_bytes

    def delete(self, key: str) -> bool:
        """Delete a key from the cache."""
        if key in self._cache:
            self._remove(key)
            return True
        return False

    def clear(self) -> None:
        """Clear the entire cache."""
        self._cache.clear()
        self._current_memory = 0

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count of removed entries."""
        expired_keys = [k for k, v in self._cache.items() if v.is_expired]
        for key in expired_keys:
            self._remove(key)
        return len(expired_keys)

    def _remove(self, key: str) -> None:
        """Remove an entry from the cache."""
        entry = self._cache.pop(key, None)
        if entry:
            self._current_memory -= entry.size_bytes

    def _evict_lru(self) -> None:
        """Evict the least recently used entry."""
        if self._cache:
            key, entry = self._cache.popitem(last=False)
            self._current_memory -= entry.size_bytes
            self._evictions += 1

    @property
    def size(self) -> int:
        """Number of entries in the cache."""
        return len(self._cache)

    @property
    def hit_rate(self) -> float:
        """Cache hit rate."""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "size": self.size,
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self.hit_rate,
            "evictions": self._evictions,
            "memory_used_bytes": self._current_memory,
            "memory_limit_bytes": self.max_memory_bytes,
        }
