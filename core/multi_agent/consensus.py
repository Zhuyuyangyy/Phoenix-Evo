"""Consensus mechanisms for multi-agent decision making."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ConsensusMethod(Enum):
    VOTE = "vote"
    REVIEW = "review"
    CHALLENGE = "challenge"


@dataclass
class Vote:
    """A single vote in a consensus round."""
    voter_id: str
    choice: Any
    confidence: float = 1.0
    reasoning: str = ""


@dataclass
class ConsensusResult:
    """Result of a consensus process."""
    proposal_id: str
    method: ConsensusMethod
    votes: List[Vote]
    outcome: Any
    agreement_ratio: float
    passed: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConsensusMechanism:
    """Implements consensus through voting, review, and challenge.

    Three modes:
    - Vote: Simple majority or supermajority voting
    - Review: Sequential review with approval/rejection
    - Challenge: Adversarial review where agents challenge proposals
    """

    def __init__(
        self,
        vote_threshold: float = 0.5,
        supermajority_threshold: float = 0.67,
        review_required_approvals: int = 2,
    ):
        self.vote_threshold = vote_threshold
        self.supermajority_threshold = supermajority_threshold
        self.review_required_approvals = review_required_approvals
        self._results: List[ConsensusResult] = []

    def vote(
        self,
        proposal_id: str,
        votes: List[Vote],
        threshold: Optional[float] = None,
    ) -> ConsensusResult:
        """Conduct a vote on a proposal."""
        if not votes:
            return ConsensusResult(
                proposal_id=proposal_id,
                method=ConsensusMethod.VOTE,
                votes=[],
                outcome=None,
                agreement_ratio=0.0,
                passed=False,
            )

        threshold = threshold or self.vote_threshold

        # Count votes by choice
        choice_counts: Dict[Any, int] = {}
        for v in votes:
            choice_counts[v.choice] = choice_counts.get(v.choice, 0) + 1

        # Find majority choice
        total = len(votes)
        winning_choice = max(choice_counts, key=choice_counts.get)  # type: ignore[arg-type]
        winning_count = choice_counts[winning_choice]
        agreement_ratio = winning_count / total

        passed = agreement_ratio >= threshold

        result = ConsensusResult(
            proposal_id=proposal_id,
            method=ConsensusMethod.VOTE,
            votes=votes,
            outcome=winning_choice,
            agreement_ratio=agreement_ratio,
            passed=passed,
        )
        self._results.append(result)
        return result

    def review(
        self,
        proposal_id: str,
        reviews: List[Vote],
        required_approvals: Optional[int] = None,
    ) -> ConsensusResult:
        """Conduct a sequential review of a proposal."""
        required = required_approvals or self.review_required_approvals

        approvals = sum(1 for r in reviews if r.choice is True or r.choice == "approve")
        rejections = sum(1 for r in reviews if r.choice is False or r.choice == "reject")

        total = len(reviews)
        agreement_ratio = approvals / total if total > 0 else 0.0
        passed = approvals >= required and rejections == 0

        result = ConsensusResult(
            proposal_id=proposal_id,
            method=ConsensusMethod.REVIEW,
            votes=reviews,
            outcome="approved" if passed else "rejected",
            agreement_ratio=agreement_ratio,
            passed=passed,
        )
        self._results.append(result)
        return result

    def challenge(
        self,
        proposal_id: str,
        proposer: Vote,
        challengers: List[Vote],
    ) -> ConsensusResult:
        """Conduct an adversarial challenge on a proposal.

        The proposer argues for the proposal, challengers try to find flaws.
        Proposal passes only if no successful challenge is mounted.
        """
        successful_challenges = sum(
            1 for c in challengers
            if c.choice is False or c.choice == "challenge" or c.choice == "reject"
        )

        total_challengers = len(challengers)
        agreement_ratio = 1.0 - (successful_challenges / total_challengers) if total_challengers > 0 else 1.0

        # Proposal passes only if no challenges succeed
        passed = successful_challenges == 0

        result = ConsensusResult(
            proposal_id=proposal_id,
            method=ConsensusMethod.CHALLENGE,
            votes=[proposer] + challengers,
            outcome="upheld" if passed else "overturned",
            agreement_ratio=agreement_ratio,
            passed=passed,
        )
        self._results.append(result)
        return result

    def get_history(self) -> List[ConsensusResult]:
        """Get the history of consensus results."""
        return list(self._results)
