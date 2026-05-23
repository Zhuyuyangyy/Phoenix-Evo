# -*- coding: utf-8 -*-
"""
SkillRetriever: Phoenix active skills router for runtime skill dispatch
V0.6 - Phoenix-Evo Runtime Skill Router

Capabilities:
  1. Load active skills from skills/active/ and build SkillCard index
  2. Search by keyword/tag/similarity to find relevant skills
  3. Filter by task_type/risk_level to narrow candidates
  4. Rank by relevance/evidence_score and return top candidates

Ranks candidates by relevance*quality_score to surface the best skill for the task.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from core.skill_registry import SkillRegistry


# Chinese character segmentation: each CJK char = one word token
# English/numbers split by word boundaries
_CHINESE_CHAR_RE = re.compile(r'[\u4e00-\u9fff]')
_ENGLISH_TOKEN_RE = re.compile(r'[A-Za-z0-9]+')


def _word_split(text: str) -> set[str]:
    """
    Split text into word tokens.
    - Chinese characters: each CJK char = one token (handles unknown-word segmentation)
    - English/numbers: split by word boundaries
    - Returns lowercase tokens as a set.

    Example:
      "WSL路径编码问题" -> {'wsl', '路径', '编码', '问题'}
      "WSL路径WSL编码null字符" -> {'路径', '编码', 'null', '字符', 'wsl'}
    """
    tokens: list[str] = []
    tokens.extend(_CHINESE_CHAR_RE.findall(text))
    tokens.extend(t.lower() for t in _ENGLISH_TOKEN_RE.findall(text))
    return set(tokens)


class SkillRetriever:
    """Phoenix active skills router - dispatches best-matching skills at runtime"""

    # --- Constants ---
    DEFAULT_TOP_K = 5
    MIN_QUALITY_SCORE = 0.40  # Minimum quality threshold for returned skills

    def __init__(self, base_dir: Path | str | None = None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent.parent
        self.registry = SkillRegistry(root=self.base_dir)

    # ------------------------------------------------------------------ #
    # Public Retrieval API                                                 #
    # ------------------------------------------------------------------ #

    def retrieve(
        self,
        task_description: str,
        task_type: str | None = None,
        risk_level: str | None = None,
        top_k: int | None = None,
        min_quality_score: float | None = None,
        project_namespace: str | None = None,  # V1.0 P0-3: namespace filter
    ) -> list[dict[str, Any]]:
        """
        Retrieve best-matching active skills for a task.

        Args:
            task_description: Natural-language description of the task
            task_type:        Task type filter (e.g. 'code', 'debug', 'design')
            risk_level:        Risk level filter (e.g. 'safe', 'caution', 'critical')
            top_k:             Maximum number of results (default: 5)
            min_quality_score: Minimum quality threshold (default: 0.40)

        Returns:
            [
                {
                    "skill_id":       "xxx",
                    "skill_name":     "xxx",
                    "relevance_score": 0.85,   # Relevance to task_description
                    "index_entry":    {...},    # skill_index.json entry
                    "skill_card":     {...},    # Parsed SkillCard dict
                    "matched_on":     ["keyword", "task_type"],  # Match reasons
                },
                ...
            ]
        """
        top_k = top_k or self.DEFAULT_TOP_K
        min_quality = min_quality_score if min_quality_score is not None else self.MIN_QUALITY_SCORE

        # 1. Load all active skills
        active_entries = self.registry.get_active_skills()

        # V1.0 P0-3: project_namespace filter
        # project_namespace=None -> all namespaces
        # project_namespace="TCM-Mind-RAG" -> only that project's skills
        if project_namespace:
            active_entries = [
                e for e in active_entries
                if e.get("project") == project_namespace
            ]

        # 2. Load skill_card for each candidate
        candidates: list[dict[str, Any]] = []
        for entry in active_entries:
            skill_id = entry.get("skill_id", "")
            quality = float(entry.get("quality_score", 0.0))

            # Skip low-quality skills
            if quality < min_quality:
                continue

            # Load SkillCard
            card = self._load_skill_card(skill_id, "active")
            if card is None:
                continue

            # 3. Compute relevance score
            relevance, matched_on = self._compute_relevance(
                task_description, task_type, risk_level, entry, card
            )

            if relevance <= 0:
                continue

            candidates.append({
                "skill_id":        skill_id,
                "skill_name":      entry.get("skill_name", skill_id),
                "relevance_score": round(relevance, 3),
                "index_entry":     entry,
                "skill_card":      card,
                "matched_on":      matched_on,
            })

        # 4. Sort by relevance_score * quality_score
        candidates.sort(
            key=lambda x: x["relevance_score"] * x["index_entry"].get("quality_score", 0.5),
            reverse=True,
        )

        return candidates[:top_k]

    def retrieve_by_keyword(
        self,
        keyword: str,
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve skills by keyword search across skill_name/procedure/tags"""
        top_k = top_k or self.DEFAULT_TOP_K
        active_entries = self.registry.get_active_skills()
        results: list[dict[str, Any]] = []

        kw_lower = keyword.lower()
        for entry in active_entries:
            skill_id = entry.get("skill_id", "")
            card = self._load_skill_card(skill_id, "active")
            if card is None:
                continue

            # Search in skill_name/procedure/when_to_use/risk_tags
            text = " ".join([
                skill_id.lower(),
                entry.get("skill_name", "").lower(),
                card.get("procedure", "").lower(),
                card.get("when_to_use", "").lower(),
                " ".join(card.get("risk_tags", [])),
            ])
            if kw_lower in text:
                results.append({
                    "skill_id":        skill_id,
                    "skill_name":      entry.get("skill_name", skill_id),
                    "relevance_score": 0.9,
                    "index_entry":     entry,
                    "skill_card":      card,
                    "matched_on":      ["keyword"],
                })

        results.sort(key=lambda x: x["index_entry"].get("quality_score", 0), reverse=True)
        return results[:top_k]

    # ------------------------------------------------------------------ #
    # Internal Scoring                                                     #
    # ------------------------------------------------------------------ #

    def _compute_relevance(
        self,
        task_description: str,
        task_type: str | None,
        risk_level: str | None,
        index_entry: dict[str, Any],
        card: dict[str, Any],
    ) -> tuple[float, list[str]]:
        """
        Compute relevance between task_description and a skill.
        Returns (score 0.0~1.0, matched_on[]).
        
        Scoring: task_type match + when_to_use overlap + name match + procedure match + risk_level match
        """
        score = 0.0
        matched: list[str] = []

        desc_words = _word_split(task_description)
        if not desc_words:
            desc_words = {task_description.lower().strip()}

        # ---- 1. task_type exact match ----
        if task_type:
            card_type = index_entry.get("task_type", "")
            if card_type and task_type.lower() == card_type.lower():
                score += 0.30
                matched.append("task_type")

        # ---- 2. when_to_use word overlap ----
        when_to_use = card.get("when to use", card.get("when_to_use", "")).lower()
        if when_to_use:
            card_words = _word_split(when_to_use)
            overlap = desc_words & card_words
            if overlap:
                # Jaccard-like
                union = desc_words | card_words
                sim = len(overlap) / max(len(union), 1)
                score += 0.35 * (1 + sim)  # overlap boost
                matched.append("when_to_use")

        # ---- 3. skill_name / skill_id match ----
        skill_name = index_entry.get("skill_name", "").lower()
        skill_id_lower = index_entry.get("skill_id", "").lower()
        name_words = _word_split(skill_name)
        id_words = _word_split(skill_id_lower)
        if desc_words & (name_words | id_words):
            score += 0.15
            matched.append("name")

        # ---- 4. procedure word overlap ----
        procedure = card.get("procedure", "").lower()
        if procedure:
            proc_words = _word_split(procedure)
            if desc_words & proc_words:
                score += 0.10
                matched.append("procedure")

        # ---- 5. risk_level match ----
        if risk_level and index_entry.get("risk_level"):
            if risk_level.lower() == index_entry.get("risk_level").lower():
                score += 0.10
                matched.append("risk_level")

        # Clamp and return
        return (min(score, 1.0), matched)

    def _load_skill_card(self, skill_id: str, status: str) -> dict[str, Any] | None:
        """Load skill .md file and parse into SkillCard dict.
        Returns None if file not found or parse fails.
        
        Search paths:
          1. Phoenix main: skills/active/{skill_id}.md
          2. Demo helper: skills/{skill_id}.md
        """
        candidates: list[Path] = []
        if status == "active":
            candidates = [
                self.base_dir / "skills" / "active" / f"{skill_id}.md",
                self.base_dir / "skills" / f"{skill_id}.md",
            ]
        elif status == "draft":
            candidates = [
                self.base_dir / "skills" / "draft" / f"{skill_id}.md",
            ]

        for file_path in candidates:
            if file_path.exists():
                try:
                    text = file_path.read_text(encoding="utf-8")
                    return self._parse_skill_card(text)
                except (UnicodeDecodeError, IOError):
                    pass
        return None

    @staticmethod
    def _parse_skill_card(text: str) -> dict[str, Any]:
        """
        Parse SkillCard markdown into a dict.
        
        Expected format:
          # Skill: xxx
          ## Metadata
          - **skill_id**: xxx
          - **status**: active
          ## When to Use
          ...
          ## Procedure
          1. xxx
        """
        card: dict[str, Any] = {}
        current_section = ""

        # Parse section headers and key-value metadata
        for line in text.splitlines():
            line_stripped = line.strip()

            # Section header
            if line_stripped.startswith("## "):
                current_section = line_stripped[3:].strip().lower()
                card[current_section] = ""
                continue

            # Metadata key-value
            if ":**" in line_stripped:
                key_end = line_stripped.index(":**", 2)
                key = line_stripped[2:key_end].strip()
                val = line_stripped[key_end + 3:].strip()
                card[key] = val
                current_section = ""
                continue

            # Procedure / Inputs / Failure Cases: list items
            if current_section in ("procedure", "inputs", "failure cases", "validation") and line.startswith(("1.", "2.", "- ", "| ")):
                existing = card.get(current_section, "")
                card[current_section] = existing + "\n" + line_stripped if existing else line_stripped
                continue

            # When to Use / Safety Note: freeform text
            if current_section in ("when to use", "safety note", "description"):
                existing = card.get(current_section, "")
                card[current_section] = (existing + " " + line_stripped).strip()
                continue

        # Extract risk_tags from Safety Note bracketed patterns
        if "risk_tags" not in card:
            safety = card.get("safety note", "")
            if safety:
                tags = re.findall(r"\[([^\]]+)\]", safety)
                if tags:
                    card["risk_tags"] = tags

        return card
