# -*- coding: utf-8 -*-
"""
SkillRetriever: ÃÂÃÂ¤ÃÂÃÂ»ÃÂÃÂ Phoenix ÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¨ÃÂÃÂÃÂÃÂ½ÃÂÃÂ¥ÃÂÃÂºÃÂÃÂÃÂÃÂ¤ÃÂÃÂ¸ÃÂÃÂ­ÃÂÃÂ¦ÃÂÃÂ£ÃÂÃÂÃÂÃÂ§ÃÂÃÂ´ÃÂÃÂ¢ active skills
V0.6 - Phoenix-Evo Runtime Skill Router

ÃÂÃÂ¨ÃÂÃÂÃÂÃÂÃÂÃÂ¨ÃÂÃÂ´ÃÂÃÂ£ÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂ
  1. ÃÂÃÂ¦ÃÂÃÂÃÂÃÂ«ÃÂÃÂ¦ÃÂÃÂÃÂÃÂ skills/active/ ÃÂÃÂ¤ÃÂÃÂ¸ÃÂÃÂÃÂÃÂ§ÃÂÃÂÃÂÃÂ SkillCard
  2. ÃÂÃÂ¦ÃÂÃÂÃÂÃÂ¯ÃÂÃÂ¦ÃÂÃÂÃÂÃÂ keyword/tag/similarity ÃÂÃÂ¥ÃÂÃÂ¤ÃÂÃÂÃÂÃÂ§ÃÂÃÂ»ÃÂÃÂ´ÃÂÃÂ¦ÃÂÃÂ£ÃÂÃÂÃÂÃÂ§ÃÂÃÂ´ÃÂÃÂ¢
  3. ÃÂÃÂ¨ÃÂÃÂ¿ÃÂÃÂÃÂÃÂ¦ÃÂÃÂ»ÃÂÃÂ¤ÃÂÃÂ©ÃÂÃÂÃÂÃÂ active ÃÂÃÂ§ÃÂÃÂÃÂÃÂ¶ÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ§ÃÂÃÂÃÂÃÂ skill
  4. ÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ§ÃÂÃÂÃÂÃÂ¸ÃÂÃÂ¥
ÃÂÃÂ³ÃÂÃÂ¦ÃÂÃÂÃÂÃÂ§/evidence_score ÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¥ÃÂÃÂºÃÂÃÂÃÂÃÂ¨ÃÂÃÂ¿ÃÂÃÂÃÂÃÂ¥ÃÂÃÂÃÂÃÂÃÂÃÂ¥ÃÂÃÂÃÂÃÂÃÂÃÂ©ÃÂÃÂÃÂÃÂÃÂÃÂ¥ÃÂÃÂÃÂÃÂÃÂÃÂ¨ÃÂÃÂ¡ÃÂÃÂ¨
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
_ENGLISH_TOKEN_RE = re.compile(r'[a-zA-Z0-9]+')


def _word_split(text: str) -> set[str]:
    """
    Split text into word tokens.
    - Chinese characters: each CJK char = one token (handles unknown-word segmentation)
    - English/numbers: split by word boundaries
    - Returns lowercase tokens as a set.

    Example:
      "WSLÃÂÃÂ¨ÃÂÃÂ·ÃÂÃÂ¯ÃÂÃÂ¥ÃÂÃÂ¾ÃÂÃÂÃÂÃÂ¤ÃÂÃÂ¿ÃÂÃÂ®ÃÂÃÂ¥ÃÂÃÂ¤ÃÂÃÂ" ÃÂÃÂ¢ÃÂÃÂÃÂÃÂ {'wsl', 'ÃÂÃÂ¨ÃÂÃÂ·ÃÂÃÂ¯', 'ÃÂÃÂ¥ÃÂÃÂ¾ÃÂÃÂ', 'ÃÂÃÂ¤ÃÂÃÂ¿ÃÂÃÂ®', 'ÃÂÃÂ¥ÃÂÃÂ¤ÃÂÃÂ'}
      "ÃÂÃÂ¤ÃÂÃÂ¿ÃÂÃÂ®ÃÂÃÂ¥ÃÂÃÂ¤ÃÂÃÂWSLÃÂÃÂ¤ÃÂÃÂ¸ÃÂÃÂ­ÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¨ÃÂÃÂ·ÃÂÃÂ¯ÃÂÃÂ¥ÃÂÃÂ¾ÃÂÃÂÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¤ÃÂÃÂ»ÃÂÃÂ¶ÃÂÃÂ¥ÃÂÃÂÃÂÃÂÃÂÃÂ¥
ÃÂÃÂ¥nullÃÂÃÂ¥ÃÂÃÂ­ÃÂÃÂÃÂÃÂ¨ÃÂÃÂÃÂÃÂ" ÃÂÃÂ¢ÃÂÃÂÃÂÃÂ {'ÃÂÃÂ¤ÃÂÃÂ¿ÃÂÃÂ®', 'ÃÂÃÂ¥ÃÂÃÂ¤ÃÂÃÂ', 'wsl', 'ÃÂÃÂ¤ÃÂÃÂ¸ÃÂÃÂ­', 'ÃÂÃÂ¦ÃÂÃÂÃÂÃÂ', 'ÃÂÃÂ¨ÃÂÃÂ·ÃÂÃÂ¯', 'ÃÂÃÂ¥ÃÂÃÂ¾ÃÂÃÂ', 'ÃÂÃÂ¦ÃÂÃÂÃÂÃÂ', 'ÃÂÃÂ¤ÃÂÃÂ»ÃÂÃÂ¶', 'ÃÂÃÂ¥ÃÂÃÂÃÂÃÂ', 'ÃÂÃÂ¥
ÃÂÃÂ¥', 'null', 'ÃÂÃÂ¥ÃÂÃÂ­ÃÂÃÂ', 'ÃÂÃÂ¨ÃÂÃÂÃÂÃÂ'}
    """
    tokens: list[str] = []
    tokens.extend(_CHINESE_CHAR_RE.findall(text))
    tokens.extend(t.lower() for t in _ENGLISH_TOKEN_RE.findall(text))
    return set(tokens)


class SkillRetriever:
    """ÃÂÃÂ¤ÃÂÃÂ»ÃÂÃÂ Phoenix active skills ÃÂÃÂ¤ÃÂÃÂ¸ÃÂÃÂ­ÃÂÃÂ¦ÃÂÃÂ£ÃÂÃÂÃÂÃÂ§ÃÂÃÂ´ÃÂÃÂ¢ÃÂÃÂ¥ÃÂÃÂÃÂÃÂÃÂÃÂ©ÃÂÃÂÃÂÃÂÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¨ÃÂÃÂÃÂÃÂ½"""

    # --- ÃÂÃÂ¦ÃÂÃÂ£ÃÂÃÂÃÂÃÂ§ÃÂÃÂ´ÃÂÃÂ¢ÃÂÃÂ©
ÃÂÃÂÃÂÃÂ§ÃÂÃÂ½ÃÂÃÂ® ---
    DEFAULT_TOP_K = 5
    MIN_QUALITY_SCORE = 0.40  # ÃÂÃÂ¤ÃÂÃÂ½ÃÂÃÂÃÂÃÂ¤ÃÂÃÂºÃÂÃÂÃÂÃÂ¦ÃÂÃÂ­ÃÂÃÂ¤ÃÂÃÂ¥ÃÂÃÂÃÂÃÂÃÂÃÂ§ÃÂÃÂÃÂÃÂ skill ÃÂÃÂ¤ÃÂÃÂ¸ÃÂÃÂÃÂÃÂ¨ÃÂÃÂ¿ÃÂÃÂÃÂÃÂ¥ÃÂÃÂÃÂÃÂ

    def __init__(self, base_dir: Path | str | None = None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent.parent
        self.registry = SkillRegistry(root=self.base_dir)

    # ------------------------------------------------------------------ #
    # ÃÂÃÂ¥
ÃÂÃÂ¬ÃÂÃÂ¥ÃÂÃÂ¼ÃÂÃÂÃÂÃÂ¦ÃÂÃÂÃÂÃÂ¥ÃÂÃÂ¥ÃÂÃÂÃÂÃÂ£                                                          #
    # ------------------------------------------------------------------ #

    def retrieve(
        self,
        task_description: str,
        task_type: str | None = None,
        risk_level: str | None = None,
        top_k: int | None = None,
        min_quality_score: float | None = None,
        project_namespace: str | None = None,  # V1.0 P0-3: ÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¨ÃÂÃÂÃÂÃÂ½ÃÂÃÂ©ÃÂÃÂ¡ÃÂÃÂ¹ÃÂÃÂ§ÃÂÃÂÃÂÃÂ®ÃÂÃÂ¥ÃÂÃÂÃÂÃÂ½ÃÂÃÂ¥ÃÂÃÂÃÂÃÂÃÂÃÂ§ÃÂÃÂ©ÃÂÃÂºÃÂÃÂ©ÃÂÃÂÃÂÃÂ´ÃÂÃÂ¨ÃÂÃÂ¿ÃÂÃÂÃÂÃÂ¦ÃÂÃÂ»ÃÂÃÂ¤
    ) -> list[dict[str, Any]]:
        """
        ÃÂÃÂ¤ÃÂÃÂ¸ÃÂÃÂ»ÃÂÃÂ¦ÃÂÃÂ£ÃÂÃÂÃÂÃÂ§ÃÂÃÂ´ÃÂÃÂ¢ÃÂÃÂ¥
ÃÂÃÂ¥ÃÂÃÂ¥ÃÂÃÂÃÂÃÂ£ÃÂÃÂ£ÃÂÃÂÃÂÃÂ

        ÃÂÃÂ¥ÃÂÃÂÃÂÃÂÃÂÃÂ¦ÃÂÃÂÃÂÃÂ°:
            task_description: ÃÂÃÂ¤ÃÂÃÂ»ÃÂÃÂ»ÃÂÃÂ¥ÃÂÃÂÃÂÃÂ¡ÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¨ÃÂÃÂ¿ÃÂÃÂ°ÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂÃÂÃÂ¦ÃÂÃÂ ÃÂÃÂ¸ÃÂÃÂ¥ÃÂÃÂ¿ÃÂÃÂÃÂÃÂ¦ÃÂÃÂ£ÃÂÃÂÃÂÃÂ§ÃÂÃÂ´ÃÂÃÂ¢ÃÂÃÂ¥ÃÂÃÂ­ÃÂÃÂÃÂÃÂ¦ÃÂÃÂ®ÃÂÃÂµÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂ
            task_type:        ÃÂÃÂ¤ÃÂÃÂ»ÃÂÃÂ»ÃÂÃÂ¥ÃÂÃÂÃÂÃÂ¡ÃÂÃÂ§ÃÂÃÂ±ÃÂÃÂ»ÃÂÃÂ¥ÃÂÃÂÃÂÃÂÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂÃÂÃÂ¥ÃÂÃÂÃÂÃÂ¯ÃÂÃÂ©ÃÂÃÂÃÂÃÂÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂÃÂÃÂ§ÃÂÃÂ²ÃÂÃÂ¾ÃÂÃÂ§ÃÂÃÂ¡ÃÂÃÂ®ÃÂÃÂ¨ÃÂÃÂ¿ÃÂÃÂÃÂÃÂ¦ÃÂÃÂ»ÃÂÃÂ¤ÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂ
            risk_level:        ÃÂÃÂ©ÃÂÃÂ£ÃÂÃÂÃÂÃÂ©ÃÂÃÂÃÂÃÂ©ÃÂÃÂ§ÃÂÃÂ­ÃÂÃÂÃÂÃÂ§ÃÂÃÂºÃÂÃÂ§ÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂÃÂÃÂ¥ÃÂÃÂÃÂÃÂ¯ÃÂÃÂ©ÃÂÃÂÃÂÃÂÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂ
            top_k:             ÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¥ÃÂÃÂ¤ÃÂÃÂÃÂÃÂ¨ÃÂÃÂ¿ÃÂÃÂÃÂÃÂ¥ÃÂÃÂÃÂÃÂÃÂÃÂ¦ÃÂÃÂÃÂÃÂ°ÃÂÃÂ©ÃÂÃÂÃÂÃÂÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂÃÂÃÂ©ÃÂÃÂ»ÃÂÃÂÃÂÃÂ¨ÃÂÃÂ®ÃÂÃÂ¤ 5ÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂ
            min_quality_score: ÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¤ÃÂÃÂ½ÃÂÃÂÃÂÃÂ¨ÃÂÃÂ´ÃÂÃÂ¨ÃÂÃÂ©ÃÂÃÂÃÂÃÂÃÂÃÂ¥ÃÂÃÂÃÂÃÂÃÂÃÂ¨ÃÂÃÂ¿ÃÂÃÂÃÂÃÂ¦ÃÂÃÂ»ÃÂÃÂ¤ÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂÃÂÃÂ©ÃÂÃÂ»ÃÂÃÂÃÂÃÂ¨ÃÂÃÂ®ÃÂÃÂ¤ 0.40ÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂ

        ÃÂÃÂ¨ÃÂÃÂ¿ÃÂÃÂÃÂÃÂ¥ÃÂÃÂÃÂÃÂ:
            [
                {
                    "skill_id":       "xxx",
                    "skill_name":     "xxx",
                    "relevance_score": 0.85,   # ÃÂÃÂ¤ÃÂÃÂ¸ÃÂÃÂ task_description ÃÂÃÂ§ÃÂÃÂÃÂÃÂÃÂÃÂ§ÃÂÃÂÃÂÃÂ¸ÃÂÃÂ¥
ÃÂÃÂ³ÃÂÃÂ¥ÃÂÃÂºÃÂÃÂ¦
                    "index_entry":    {...},    # skill_index.json ÃÂÃÂ¤ÃÂÃÂ¸ÃÂÃÂ­ÃÂÃÂ§ÃÂÃÂÃÂÃÂÃÂÃÂ¥ÃÂÃÂ®ÃÂÃÂÃÂÃÂ¦ÃÂÃÂÃÂÃÂ´ÃÂÃÂ¦ÃÂÃÂÃÂÃÂ¡ÃÂÃÂ§ÃÂÃÂÃÂÃÂ®
                    "skill_card":     {...},    # ÃÂÃÂ¨ÃÂÃÂ§ÃÂÃÂ£ÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¥ÃÂÃÂÃÂÃÂÃÂÃÂ§ÃÂÃÂÃÂÃÂ SkillCard dict
                    "matched_on":     ["keyword", "task_type"],  # ÃÂÃÂ¥ÃÂÃÂÃÂÃÂ½ÃÂÃÂ¤ÃÂÃÂ¸ÃÂÃÂ­ÃÂÃÂ¥ÃÂÃÂÃÂÃÂÃÂÃÂ¥ÃÂÃÂÃÂÃÂ 
                },
                ...
            ]
        """
        top_k = top_k or self.DEFAULT_TOP_K
        min_quality = min_quality_score if min_quality_score is not None else self.MIN_QUALITY_SCORE

        # 1. ÃÂÃÂ¨ÃÂÃÂÃÂÃÂ·ÃÂÃÂ¥ÃÂÃÂÃÂÃÂÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¦ÃÂÃÂÃÂÃÂ active skills
        active_entries = self.registry.get_active_skills()

        # V1.0 P0-3: project_namespace ÃÂÃÂ¨ÃÂÃÂ¿ÃÂÃÂÃÂÃÂ¦ÃÂÃÂ»ÃÂÃÂ¤
        # project_namespace=None ÃÂÃÂ¢ÃÂÃÂÃÂÃÂ ÃÂÃÂ¤ÃÂÃÂ¸ÃÂÃÂÃÂÃÂ¨ÃÂÃÂ¿ÃÂÃÂÃÂÃÂ¦ÃÂÃÂ»ÃÂÃÂ¤ÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂÃÂÃÂ¨ÃÂÃÂ¿ÃÂÃÂÃÂÃÂ¥ÃÂÃÂÃÂÃÂÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¦ÃÂÃÂ´ÃÂÃÂ»ÃÂÃÂ¨ÃÂÃÂ·ÃÂÃÂÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¨ÃÂÃÂÃÂÃÂ½ÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂÃÂÃÂ¥
ÃÂÃÂ¼ÃÂÃÂ¥ÃÂÃÂ®ÃÂÃÂ¹ÃÂÃÂ¦ÃÂÃÂÃÂÃÂ ÃÂÃÂ©ÃÂÃÂ¡ÃÂÃÂ¹ÃÂÃÂ§ÃÂÃÂÃÂÃÂ®ÃÂÃÂ¦ÃÂÃÂ ÃÂÃÂÃÂÃÂ§ÃÂÃÂ­ÃÂÃÂ¾ÃÂÃÂ§ÃÂÃÂÃÂÃÂÃÂÃÂ¨ÃÂÃÂÃÂÃÂÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¨ÃÂÃÂÃÂÃÂ½ÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂ
        # project_namespace="TCM-Mind-RAG" ÃÂÃÂ¢ÃÂÃÂÃÂÃÂ ÃÂÃÂ¥ÃÂÃÂÃÂÃÂªÃÂÃÂ¨ÃÂÃÂ¿ÃÂÃÂÃÂÃÂ¥ÃÂÃÂÃÂÃÂ project=TCM-Mind-RAG ÃÂÃÂ§ÃÂÃÂÃÂÃÂÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¨ÃÂÃÂÃÂÃÂ½
        if project_namespace:
            active_entries = [
                e for e in active_entries
                if e.get("project") == project_namespace
            ]

        # 2. ÃÂÃÂ¨ÃÂÃÂ§ÃÂÃÂ£ÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¦ÃÂÃÂ¯ÃÂÃÂÃÂÃÂ¤ÃÂÃÂ¸ÃÂÃÂª skill_card ÃÂÃÂ¤ÃÂÃÂ¸ÃÂÃÂ°ÃÂÃÂ¥ÃÂÃÂ¯ÃÂÃÂÃÂÃÂ§ÃÂÃÂ´ÃÂÃÂ¢ÃÂÃÂ¥ÃÂÃÂ¼ÃÂÃÂÃÂÃÂ¦ÃÂÃÂÃÂÃÂ°ÃÂÃÂ¦ÃÂÃÂÃÂÃÂ®
        candidates: list[dict[str, Any]] = []
        for entry in active_entries:
            skill_id = entry.get("skill_id", "")
            quality = float(entry.get("quality_score", 0.0))

            # ÃÂÃÂ¨ÃÂÃÂ´ÃÂÃÂ¨ÃÂÃÂ©ÃÂÃÂÃÂÃÂÃÂÃÂ¨ÃÂÃÂ¿ÃÂÃÂÃÂÃÂ¦ÃÂÃÂ»ÃÂÃÂ¤ÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂÃÂÃÂ¤ÃÂÃÂ¸ÃÂÃÂ¥ÃÂÃÂ¦ÃÂÃÂ ÃÂÃÂ¼ÃÂÃÂ¥ÃÂÃÂ°ÃÂÃÂÃÂÃÂ¤ÃÂÃÂºÃÂÃÂÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂ
            if quality < min_quality:
                continue

            # ÃÂÃÂ¨ÃÂÃÂ¯ÃÂÃÂ»ÃÂÃÂ¥ÃÂÃÂÃÂÃÂ SkillCard ÃÂÃÂ¥ÃÂÃÂ®ÃÂÃÂÃÂÃÂ¦ÃÂÃÂÃÂÃÂ´ÃÂÃÂ¥ÃÂÃÂ
ÃÂÃÂ¥ÃÂÃÂ®ÃÂÃÂ¹
            card = self._load_skill_card(skill_id, "active")
            if card is None:
                continue

            # 3. ÃÂÃÂ¨ÃÂÃÂ®ÃÂÃÂ¡ÃÂÃÂ§ÃÂÃÂ®ÃÂÃÂÃÂÃÂ§ÃÂÃÂÃÂÃÂ¸ÃÂÃÂ¥
ÃÂÃÂ³ÃÂÃÂ¥ÃÂÃÂºÃÂÃÂ¦
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

        # 4. ÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¥ÃÂÃÂºÃÂÃÂÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂrelevance_score * quality_score
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
        """ÃÂÃÂ§ÃÂÃÂºÃÂÃÂ¯ÃÂÃÂ¥
ÃÂÃÂ³ÃÂÃÂ©ÃÂÃÂÃÂÃÂ®ÃÂÃÂ¨ÃÂÃÂ¯ÃÂÃÂÃÂÃÂ¦ÃÂÃÂ£ÃÂÃÂÃÂÃÂ§ÃÂÃÂ´ÃÂÃÂ¢ÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂÃÂÃÂ§ÃÂÃÂÃÂÃÂ¨ÃÂÃÂ¤ÃÂÃÂºÃÂÃÂÃÂÃÂ¥ÃÂÃÂ·ÃÂÃÂ¥ÃÂÃÂ¥
ÃÂÃÂ·ÃÂÃÂ©ÃÂÃÂÃÂÃÂÃÂÃÂ¨ÃÂÃÂ¯ÃÂÃÂ¯ÃÂÃÂ§ÃÂÃÂ ÃÂÃÂÃÂÃÂ£ÃÂÃÂÃÂÃÂÃÂÃÂ¥ÃÂÃÂ·ÃÂÃÂ¥ÃÂÃÂ¥
ÃÂÃÂ·ÃÂÃÂ¥ÃÂÃÂÃÂÃÂÃÂÃÂ§ÃÂÃÂ­ÃÂÃÂÃÂÃÂ§ÃÂÃÂ²ÃÂÃÂ¾ÃÂÃÂ§ÃÂÃÂ¡ÃÂÃÂ®ÃÂÃÂ¥ÃÂÃÂÃÂÃÂ¹ÃÂÃÂ©
ÃÂÃÂÃÂÃÂ¥ÃÂÃÂÃÂÃÂºÃÂÃÂ¦ÃÂÃÂÃÂÃÂ¯ÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂ"""
        top_k = top_k or self.DEFAULT_TOP_K
        active_entries = self.registry.get_active_skills()
        results: list[dict[str, Any]] = []

        kw_lower = keyword.lower()
        for entry in active_entries:
            skill_id = entry.get("skill_id", "")
            card = self._load_skill_card(skill_id, "active")
            if card is None:
                continue

            # ÃÂÃÂ¥
ÃÂÃÂ³ÃÂÃÂ©ÃÂÃÂÃÂÃÂ®ÃÂÃÂ¨ÃÂÃÂ¯ÃÂÃÂÃÂÃÂ¥ÃÂÃÂÃÂÃÂ½ÃÂÃÂ¤ÃÂÃÂ¸ÃÂÃÂ­ÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂskill_name / skill_id / procedure / when_to_use
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
    # ÃÂÃÂ¥ÃÂÃÂ
ÃÂÃÂ©ÃÂÃÂÃÂÃÂ¨ÃÂÃÂ¥ÃÂÃÂ®ÃÂÃÂÃÂÃÂ§ÃÂÃÂÃÂÃÂ°                                                          #
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
        ÃÂÃÂ¨ÃÂÃÂ®ÃÂÃÂ¡ÃÂÃÂ§ÃÂÃÂ®ÃÂÃÂ task_description ÃÂÃÂ¤ÃÂÃÂ¸ÃÂÃÂ skill ÃÂÃÂ§ÃÂÃÂÃÂÃÂÃÂÃÂ§ÃÂÃÂÃÂÃÂ¸ÃÂÃÂ¥
ÃÂÃÂ³ÃÂÃÂ¥ÃÂÃÂºÃÂÃÂ¦ÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂ0.0 ~ 1.0ÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂÃÂÃÂ£ÃÂÃÂÃÂÃÂ
        ÃÂÃÂ¤ÃÂÃÂ½ÃÂÃÂ¿ÃÂÃÂ§ÃÂÃÂÃÂÃÂ¨ÃÂÃÂ¤ÃÂÃÂ¸ÃÂÃÂ­ÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¥ÃÂÃÂ­ÃÂÃÂÃÂÃÂ§ÃÂÃÂ¬ÃÂÃÂ¦ÃÂÃÂ¥ÃÂÃÂÃÂÃÂÃÂÃÂ¨ÃÂÃÂ¯ÃÂÃÂ + ÃÂÃÂ¨ÃÂÃÂÃÂÃÂ±ÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¥ÃÂÃÂÃÂÃÂÃÂÃÂ¨ÃÂÃÂ¯ÃÂÃÂÃÂÃÂ¥ÃÂÃÂÃÂÃÂÃÂÃÂ¨ÃÂÃÂ¯ÃÂÃÂÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂÃÂÃÂ¨ÃÂÃÂ§ÃÂÃÂ£ÃÂÃÂ¥ÃÂÃÂÃÂÃÂ³ÃÂÃÂ¨ÃÂÃÂ¿ÃÂÃÂÃÂÃÂ§ÃÂÃÂ»ÃÂÃÂ­ÃÂÃÂ¤ÃÂÃÂ¸ÃÂÃÂ­ÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¦ÃÂÃÂÃÂÃÂ ÃÂÃÂ¦ÃÂÃÂ³ÃÂÃÂÃÂÃÂ¥ÃÂÃÂÃÂÃÂ¹ÃÂÃÂ©
ÃÂÃÂÃÂÃÂ§ÃÂÃÂÃÂÃÂÃÂÃÂ©ÃÂÃÂÃÂÃÂ®ÃÂÃÂ©ÃÂÃÂ¢ÃÂÃÂÃÂÃÂ£ÃÂÃÂÃÂÃÂ
        ÃÂÃÂ¨ÃÂÃÂ¿ÃÂÃÂÃÂÃÂ¥ÃÂÃÂÃÂÃÂ (relevance_score, matched_on[])
        """
        score = 0.0
        matched: list[str] = []

        desc_words = _word_split(task_description)
        if not desc_words:
            desc_words = {task_description.lower().strip()}

        # ---- 1. task_type ÃÂÃÂ§ÃÂÃÂ²ÃÂÃÂ¾ÃÂÃÂ§ÃÂÃÂ¡ÃÂÃÂ®ÃÂÃÂ¥ÃÂÃÂÃÂÃÂ¹ÃÂÃÂ©
ÃÂÃÂÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ©ÃÂÃÂÃÂÃÂÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ©ÃÂÃÂ«ÃÂÃÂÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂ----
        if task_type:
            card_type = index_entry.get("task_type", "")
            if card_type and task_type.lower() == card_type.lower():
                score += 0.30
                matched.append("task_type")

        # ---- 2. when_to_use ÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¨ÃÂÃÂ¿ÃÂÃÂ°ÃÂÃÂ§ÃÂÃÂÃÂÃÂ¸ÃÂÃÂ¤ÃÂÃÂ¼ÃÂÃÂ¼ÃÂÃÂ¥ÃÂÃÂºÃÂÃÂ¦ÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂÃÂÃÂ©ÃÂÃÂ«ÃÂÃÂÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ©ÃÂÃÂÃÂÃÂÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂ----
        when_to_use = card.get("when to use", card.get("when_to_use", "")).lower()
        if when_to_use:
            card_words = _word_split(when_to_use)
            overlap = desc_words & card_words
            if overlap:
                # Jaccard-like
                union = desc_words | card_words
                sim = len(overlap) / max(len(union), 1)
                score += 0.35 * (1 + sim)  # ÃÂÃÂ¦ÃÂÃÂÃÂÃÂoverlapÃÂÃÂ¦ÃÂÃÂÃÂÃÂ¶ boost
                matched.append("when_to_use")

        # ---- 3. skill_name / skill_id ÃÂÃÂ¨ÃÂÃÂ¯ÃÂÃÂÃÂÃÂ¥ÃÂÃÂÃÂÃÂ¹ÃÂÃÂ©
ÃÂÃÂ ----
        skill_name = index_entry.get("skill_name", "").lower()
        skill_id_lower = index_entry.get("skill_id", "").lower()
        name_words = _word_split(skill_name)
        id_words = _word_split(skill_id_lower)
        if desc_words & (name_words | id_words):
            score += 0.15
            matched.append("name")

        # ---- 4. procedure ÃÂÃÂ¦ÃÂÃÂ­ÃÂÃÂ¥ÃÂÃÂ©ÃÂÃÂªÃÂÃÂ¤ÃÂÃÂ¥
ÃÂÃÂ³ÃÂÃÂ©ÃÂÃÂÃÂÃÂ®ÃÂÃÂ¨ÃÂÃÂ¯ÃÂÃÂÃÂÃÂ¥ÃÂÃÂÃÂÃÂ¹ÃÂÃÂ©
ÃÂÃÂ ----
        procedure = card.get("procedure", "").lower()
        if procedure:
            proc_words = _word_split(procedure)
            if desc_words & proc_words:
                score += 0.10
                matched.append("procedure")

        # ---- 5. risk_level ÃÂÃÂ¤ÃÂÃÂ¸ÃÂÃÂÃÂÃÂ¨ÃÂÃÂÃÂÃÂ´ÃÂÃÂ¦ÃÂÃÂÃÂÃÂ§ ----
        if risk_level and index_entry.get("risk_level"):
            if risk_level.lower() == index_entry.get("risk_level").lower():
                score += 0.10
                matched.append("risk_level")

        # ÃÂÃÂ¥ÃÂÃÂ½ÃÂÃÂÃÂÃÂ¤ÃÂÃÂ¸ÃÂÃÂÃÂÃÂ¥ÃÂÃÂÃÂÃÂÃÂÃÂ¤ÃÂÃÂ¸ÃÂÃÂÃÂÃÂ©ÃÂÃÂÃÂÃÂ
        return (min(score, 1.0), matched)

    def _load_skill_card(self, skill_id: str, status: str) -> dict[str, Any] | None:
        """ÃÂÃÂ¨ÃÂÃÂ§ÃÂÃÂ£ÃÂÃÂ¦ÃÂÃÂÃÂÃÂ skill .md ÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¤ÃÂÃÂ»ÃÂÃÂ¶ÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¥ÃÂÃÂÃÂÃÂ frontmatter + ÃÂÃÂ¥ÃÂÃÂ
        return None
        ÃÂÃÂ¥
ÃÂÃÂ¼ÃÂÃÂ¥ÃÂÃÂ®ÃÂÃÂ¹ÃÂÃÂ¤ÃÂÃÂ¸ÃÂÃÂ¤ÃÂÃÂ§ÃÂÃÂ§ÃÂÃÂÃÂÃÂ§ÃÂÃÂÃÂÃÂ®ÃÂÃÂ¥ÃÂÃÂ½ÃÂÃÂÃÂÃÂ§ÃÂÃÂ»ÃÂÃÂÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂ
          1. Phoenix ÃÂÃÂ¥ÃÂÃÂÃÂÃÂÃÂÃÂ§ÃÂÃÂÃÂÃÂÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂskills/active/{skill_id}.md
          2. demo helperÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂskills/{skill_id}.md
        """
        candidates: list[Path] = []
        if status == "active":
            candidates = [
                self.base_dir / "skills" / "active" / f"{skill_id}.md",
                self.base_dir / "skills" / f"{skill_id}.md",         # demo helper ÃÂÃÂ¥ÃÂÃÂÃÂÃÂÃÂÃÂ¥
ÃÂÃÂ¥ÃÂÃÂ¤ÃÂÃÂ½ÃÂÃÂÃÂÃÂ§ÃÂÃÂ½ÃÂÃÂ®
            ]
        elif status == "draft":
            candidates = [
                self.base_dir / "skills" / "draft" / f"{skill_id}.md",
            ]

        for file_path in candidates:
            if file_path.exists():
                try:
                    text = file_path.read_text(encoding="utf-8")
        return None
                except (UnicodeDecodeError, IOError):
                    pass
        return None

    @staticmethod
        return None
        """
        ÃÂÃÂ¨ÃÂÃÂ§ÃÂÃÂ£ÃÂÃÂ¦ÃÂÃÂÃÂÃÂ SkillCard markdown ÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¦ÃÂÃÂÃÂÃÂ¬ÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¥ÃÂÃÂÃÂÃÂÃÂÃÂ¥
ÃÂÃÂÃÂÃÂ¦ÃÂÃÂÃÂÃÂ°ÃÂÃÂ¦ÃÂÃÂÃÂÃÂ®ÃÂÃÂ¥ÃÂÃÂ­ÃÂÃÂÃÂÃÂ¦ÃÂÃÂ®ÃÂÃÂµÃÂÃÂ£ÃÂÃÂÃÂÃÂ
        ÃÂÃÂ¦ÃÂÃÂ ÃÂÃÂ¼ÃÂÃÂ¥ÃÂÃÂ¼ÃÂÃÂÃÂÃÂ¦ÃÂÃÂ¦ÃÂÃÂÃÂÃÂ¨ÃÂÃÂ§ÃÂÃÂÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂ
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

        # ÃÂÃÂ§ÃÂÃÂ®ÃÂÃÂÃÂÃÂ¥ÃÂÃÂÃÂÃÂÃÂÃÂ¨ÃÂÃÂ¡ÃÂÃÂÃÂÃÂ§ÃÂÃÂºÃÂÃÂ§ÃÂÃÂ¨ÃÂÃÂ§ÃÂÃÂ£ÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂÃÂÃÂ¤ÃÂÃÂ¸ÃÂÃÂÃÂÃÂ¥ÃÂÃÂÃÂÃÂÃÂÃÂ¥ÃÂÃÂ®ÃÂÃÂÃÂÃÂ¦ÃÂÃÂÃÂÃÂ´ Markdown parserÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂ
        for line in text.splitlines():
            line_stripped = line.strip()

            # ÃÂÃÂ¨ÃÂÃÂÃÂÃÂÃÂÃÂ¦ÃÂÃÂ ÃÂÃÂÃÂÃÂ©ÃÂÃÂ¢ÃÂÃÂ
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

            # ÃÂÃÂ¥ÃÂÃÂÃÂÃÂÃÂÃÂ¨ÃÂÃÂ¡ÃÂÃÂ¨ÃÂÃÂ©ÃÂÃÂ¡ÃÂÃÂ¹ÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂProcedure / Inputs / Failure CasesÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂ
            if current_section in ("procedure", "inputs", "failure cases", "validation") and line.startswith(("1.", "2.", "- ", "| ")):
                existing = card.get(current_section, "")
                card[current_section] = existing + "\n" + line_stripped if existing else line_stripped
                continue

            # When to Use / Safety NoteÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂÃÂÃÂ¦ÃÂÃÂ®ÃÂÃÂµÃÂÃÂ¨ÃÂÃÂÃÂÃÂ½ÃÂÃÂ¯ÃÂÃÂ¼ÃÂÃÂ
            if current_section in ("when to use", "safety note", "description"):
                existing = card.get(current_section, "")
                card[current_section] = (existing + " " + line_stripped).strip()
                continue

        # risk_tags ÃÂÃÂ¥ÃÂÃÂÃÂÃÂ¯ÃÂÃÂ¨ÃÂÃÂÃÂÃÂ½ÃÂÃÂ¥ÃÂÃÂÃÂÃÂ¨ÃÂÃÂ¥ÃÂÃÂ
ÃÂÃÂ¨ÃÂÃÂÃÂÃÂÃÂÃÂ¥ÃÂÃÂÃÂÃÂÃÂÃÂ¨ÃÂÃÂ¡ÃÂÃÂ¨ÃÂÃÂ¤ÃÂÃÂ¸ÃÂÃÂ­
        if "risk_tags" not in card:
            # ÃÂÃÂ¥ÃÂÃÂ°ÃÂÃÂÃÂÃÂ¨ÃÂÃÂ¯ÃÂÃÂÃÂÃÂ¤ÃÂÃÂ»ÃÂÃÂ Safety Note ÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¥
ÃÂÃÂ¶ÃÂÃÂ¤ÃÂÃÂ»ÃÂÃÂÃÂÃÂ¦ÃÂÃÂ®ÃÂÃÂµÃÂÃÂ¦ÃÂÃÂÃÂÃÂÃÂÃÂ¥ÃÂÃÂÃÂÃÂ
            safety = card.get("safety note", "")
            if safety:
                tags = re.findall(r"\[([^\]]+)\]", safety)
                if tags:
                    card["risk_tags"] = tags

        return card
