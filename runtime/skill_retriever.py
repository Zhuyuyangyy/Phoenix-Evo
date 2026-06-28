"""
SkillRetriever: Phoenix active skills router for runtime skill dispatch
V0.6 - Phoenix-Evo Runtime Skill Router

Capabilities:
  1. Load active skills from skills/active/ and build SkillCard index
  2. Search by keyword/tag/similarity to find relevant skills
  3. Filter by task_type/risk_level to narrow candidates
  4. Rank by relevance/evidence_score and return top candidates

Ranks candidates by relevance*quality_score to surface the best skill for the task.

V1.1: Upgraded from Jaccard word overlap to TF-IDF + cosine similarity for
      semantic retrieval. Keyword path retained as fallback via retrieve_by_keyword().

V1.2: Upgraded primary retrieval to sentence-embedding-based semantic search
      using sentence-transformers (all-MiniLM-L6-v2). TF-IDF retained as fallback
      when sentence-transformers is not installed. This addresses Q2 SCI Review
      Finding #1: TF-IDF cannot capture semantic similarity between paraphrases.
"""

import re
from pathlib import Path
from typing import Any

from core.skill_registry import SkillRegistry

# V1.2: Import semantic retriever for sentence-embedding-based search
try:
    from .semantic_retriever import _EMBEDDING_AVAILABLE, SemanticRetriever
except ImportError:
    _EMBEDDING_AVAILABLE = False
    SemanticRetriever = None

# Import TF-IDF utilities from the dedicated module (breaks circular import)
from .tfidf_utils import (
    _JIEBA_AVAILABLE,  # noqa: F401 – re-exported for backward compat
    _compute_idf,
    _cosine_sim,
    _tfidf_vector,
    _tokenize,
    _tokenize_to_set,
    _word_split,  # noqa: F401 – re-exported for backward compat
)

# ---------------------------------------------------------------------------
# SkillRetriever
# ---------------------------------------------------------------------------

class SkillRetriever:
    """Phoenix active skills router - dispatches best-matching skills at runtime"""

    # --- Constants ---
    DEFAULT_TOP_K = 5
    MIN_QUALITY_SCORE = 0.40  # Minimum quality threshold for returned skills

    # --- Scoring weights for hybrid relevance ---
    _W_TFIDF = 0.65           # TF-IDF cosine similarity
    _W_TASK_TYPE = 0.15       # Exact task_type match bonus
    _W_RISK_LEVEL = 0.05      # Exact risk_level match bonus
    _W_NAME_BONUS = 0.10      # Name/token overlap bonus
    _W_KEYWORD_BONUS = 0.05   # When-to-use keyword overlap bonus (fallback signal)

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
        project_namespace: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve best-matching active skills for a task.

        Uses TF-IDF + cosine similarity as the primary relevance signal,
        with task_type match, risk_level match, and name overlap as bonuses.

        Args:
            task_description: Natural-language description of the task
            task_type:        Task type filter (e.g. 'code', 'debug', 'design')
            risk_level:        Risk level filter (e.g. 'safe', 'caution', 'critical')
            top_k:             Maximum number of results (default: 5)
            min_quality_score: Minimum quality threshold (default: 0.40)
            project_namespace: Optional project namespace filter

        Returns:
            [
                {
                    "skill_id":       "xxx",
                    "skill_name":     "xxx",
                    "relevance_score": 0.85,
                    "index_entry":    {...},
                    "skill_card":     {...},
                    "matched_on":     ["semantic", "task_type"],
                },
                ...
            ]
        """
        top_k = top_k or self.DEFAULT_TOP_K
        min_quality = min_quality_score if min_quality_score is not None else self.MIN_QUALITY_SCORE

        # 1. Load all active skills
        active_entries = self.registry.get_active_skills()

        # V1.0 P0-3: project_namespace filter
        if project_namespace:
            active_entries = [
                e for e in active_entries
                if e.get("project") == project_namespace
            ]

        # 2. Load skill_card for each candidate and filter by quality
        raw_candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for entry in active_entries:
            quality = float(entry.get("quality_score", 0.0))
            if quality < min_quality:
                continue
            card = self._load_skill_card(entry.get("skill_id", ""), "active")
            if card is None:
                continue
            raw_candidates.append((entry, card))

        if not raw_candidates:
            return []

        # 3. Build corpus texts for retrieval
        corpus_texts = []
        for entry, card in raw_candidates:
            corpus_texts.append(self._build_skill_text(entry, card))

        # 4. Score each candidate using semantic retrieval (V1.2)
        #    Primary: sentence-embedding cosine similarity
        #    Fallback: TF-IDF cosine similarity
        candidates: list[dict[str, Any]] = []

        # Try semantic retrieval first
        if _EMBEDDING_AVAILABLE and SemanticRetriever is not None:
            sem_retriever = SemanticRetriever()
            sem_results = sem_retriever.retrieve(
                task_description, corpus_texts, top_k=len(raw_candidates), score_threshold=0.0,
            )
            semantic_scores: dict[int, float] = {r["index"]: r["score"] for r in sem_results}

            for idx, (entry, card) in enumerate(raw_candidates):
                sem_score = semantic_scores.get(idx, 0.0)
                matched_on = []
                if sem_score > 0.1:
                    matched_on.append("semantic_embedding")

                # Hybrid scoring: semantic_embedding * 0.60 + task_type * 0.15 + risk_level * 0.05 + name_bonus * 0.10 + keyword_bonus * 0.10
                relevance = sem_score * 0.60
                if task_type and entry.get("task_type", "").lower() == (task_type or "").lower():
                    relevance += 0.15
                    matched_on.append("task_type")
                if risk_level and entry.get("risk_level", "").lower() == (risk_level or "").lower():
                    relevance += 0.05
                    matched_on.append("risk_level")
                # Name overlap bonus
                desc_tokens = _tokenize_to_set(task_description)
                name_tokens = _tokenize_to_set(entry.get("skill_name", ""))
                if desc_tokens and name_tokens and (desc_tokens & name_tokens):
                    overlap_ratio = len(desc_tokens & name_tokens) / max(len(name_tokens), 1)
                    relevance += 0.10 * overlap_ratio
                    matched_on.append("name")
                # When-to-use keyword bonus
                when_to_use = card.get("when to use", card.get("when_to_use", ""))
                if when_to_use and desc_tokens:
                    wtu_tokens = _tokenize_to_set(when_to_use)
                    if wtu_tokens and (desc_tokens & wtu_tokens):
                        jaccard = len(desc_tokens & wtu_tokens) / max(len(desc_tokens | wtu_tokens), 1)
                        relevance += 0.10 * (1 + jaccard)
                        matched_on.append("when_to_use")

                relevance = min(relevance, 1.0)
                if relevance <= 0:
                    continue
                candidates.append({
                    "skill_id":        entry.get("skill_id", ""),
                    "skill_name":      entry.get("skill_name", entry.get("skill_id", "")),
                    "relevance_score": round(relevance, 3),
                    "index_entry":     entry,
                    "skill_card":      card,
                    "matched_on":      matched_on,
                    "retrieval_method": "semantic_embedding",
                })
        else:
            # Fallback: TF-IDF path (original implementation)
            query_tokens = _tokenize(task_description)
            corpus_tokens: list[list[str]] = [query_tokens]
            for text in corpus_texts:
                corpus_tokens.append(_tokenize(text))

            idf = _compute_idf(corpus_tokens)
            query_vec = _tfidf_vector(query_tokens, idf)

            for idx, (entry, card) in enumerate(raw_candidates):
                skill_vec = _tfidf_vector(corpus_tokens[idx + 1], idf)
                relevance, matched_on = self._compute_relevance(
                    task_description, task_type, risk_level,
                    entry, card, query_vec, skill_vec,
                )
                if relevance <= 0:
                    continue
                candidates.append({
                    "skill_id":        entry.get("skill_id", ""),
                    "skill_name":      entry.get("skill_name", entry.get("skill_id", "")),
                    "relevance_score": round(relevance, 3),
                    "index_entry":     entry,
                    "skill_card":      card,
                    "matched_on":      matched_on,
                    "retrieval_method": "tfidf_fallback",
                })

        # 5. Compute evidence_score for each candidate
        for c in candidates:
            idx_entry = c["index_entry"]
            card = c["skill_card"]
            for field in ("evidence_score", "evidence_summary_score",
                          "quality_score", "confidence", "replay_confidence"):
                val = idx_entry.get(field)
                if val is not None:
                    try:
                        fval = float(val)
                        if 0.0 <= fval <= 1.0:
                            c["evidence_score"] = fval
                            break
                    except (ValueError, TypeError):
                        pass
            else:
                ev = card.get("evidence", card.get("evidence_summary", ""))
                m = re.search(r'(\d+\.?\d*)', str(ev))
                c["evidence_score"] = float(m.group(1)) / 100.0 if m else 0.50

        # 6. Sort by relevance_score * quality_score
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
        """Retrieve skills by keyword search across skill_name/procedure/tags

        This is the legacy keyword-based path, kept as a fallback for
        exact-match lookups and backward compatibility.
        """
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
            # Card keys may use spaces ("when to use") or underscores
            when_text = card.get("when_to_use", card.get("when to use", ""))
            text = " ".join([
                skill_id.lower(),
                entry.get("skill_name", "").lower(),
                card.get("procedure", "").lower(),
                when_text.lower(),
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

    @staticmethod
    def _build_skill_text(entry: dict[str, Any], card: dict[str, Any]) -> str:
        """Concatenate skill fields into a single text for TF-IDF vectorization."""
        parts: list[str] = [
            entry.get("skill_name", ""),
            card.get("when to use", card.get("when_to_use", "")),
            card.get("procedure", ""),
            card.get("description", ""),
        ]
        return " ".join(p for p in parts if p)

    def _compute_relevance(
        self,
        task_description: str,
        task_type: str | None,
        risk_level: str | None,
        index_entry: dict[str, Any],
        card: dict[str, Any],
        query_vec: dict[str, float],
        skill_vec: dict[str, float],
    ) -> tuple[float, list[str]]:
        """
        Compute hybrid relevance score between task_description and a skill.

        Primary signal: TF-IDF cosine similarity (0.0~1.0)
        Bonus signals: task_type match, risk_level match, name overlap

        Returns (score 0.0~1.0, matched_on[]).
        """
        score = 0.0
        matched: list[str] = []

        # ---- 1. TF-IDF cosine similarity (primary signal) ----
        cosine = _cosine_sim(query_vec, skill_vec)
        score += self._W_TFIDF * cosine
        if cosine > 0.05:
            matched.append("semantic")

        # ---- 2. task_type exact match ----
        if task_type:
            card_type = index_entry.get("task_type", "")
            if card_type and task_type.lower() == card_type.lower():
                score += self._W_TASK_TYPE
                matched.append("task_type")

        # ---- 3. risk_level match ----
        if risk_level and index_entry.get("risk_level"):
            if risk_level.lower() == index_entry.get("risk_level").lower():
                score += self._W_RISK_LEVEL
                matched.append("risk_level")

        # ---- 4. skill_name / skill_id overlap bonus ----
        desc_tokens = _tokenize_to_set(task_description)
        if desc_tokens:
            name_tokens = _tokenize_to_set(
                index_entry.get("skill_name", "") + " " + index_entry.get("skill_id", "")
            )
            if name_tokens and (desc_tokens & name_tokens):
                overlap_ratio = len(desc_tokens & name_tokens) / max(len(name_tokens), 1)
                score += self._W_NAME_BONUS * overlap_ratio
                matched.append("name")

        # ---- 5. when_to_use keyword overlap bonus (supplementary) ----
        when_to_use = card.get("when to use", card.get("when_to_use", ""))
        if when_to_use and desc_tokens:
            wtu_tokens = _tokenize_to_set(when_to_use)
            if wtu_tokens and (desc_tokens & wtu_tokens):
                jaccard = len(desc_tokens & wtu_tokens) / max(len(desc_tokens | wtu_tokens), 1)
                score += self._W_KEYWORD_BONUS * (1 + jaccard)
                matched.append("when_to_use")

        # Clamp and return
        return (min(score, 1.0), matched)

    def _load_skill_card(self, skill_id: str, status: str) -> dict[str, Any] | None:
        """Load skill .md file and parse into SkillCard dict.
        Returns None if file not found or parse fails.

        Search paths:
          1. Phoenix main: skills/active/{skill_id}.md
          2. Demo helper: skills/{skill_id}.md
        """
        candidates_paths: list[Path] = []
        if status == "active":
            candidates_paths = [
                self.base_dir / "skills" / "active" / f"{skill_id}.md",
                self.base_dir / "skills" / f"{skill_id}.md",
            ]
        elif status == "draft":
            candidates_paths = [
                self.base_dir / "skills" / "draft" / f"{skill_id}.md",
            ]

        for file_path in candidates_paths:
            if file_path.exists():
                try:
                    text = file_path.read_text(encoding="utf-8")
                    return self._parse_skill_card(text)
                except (OSError, UnicodeDecodeError):
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
