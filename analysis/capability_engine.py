# analysis/capability_engine.py
# AdaptLab — EMA capability score update with feature-weighted concept map.
# No LLM involved. Pure deterministic math.
# Imports from: database/db.py, database/models.py, utils/constants.py, utils/logger.py

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from database.models import CapabilityScore
from utils.constants import (
    CONCEPT_WEIGHTS,
    EMA_DEFAULT_WEIGHT,
    INITIAL_SCORE,
    SCORE_MAX,
    SCORE_MIN,
    SUBMISSION_SCORE_FULL_PASS,
    SUBMISSION_SCORE_PARTIAL_HIGH,
    SUBMISSION_SCORE_PARTIAL_LOW,
    SUBMISSION_SCORE_SYNTAX_ERROR,
    SUBMISSION_SCORE_TIMEOUT_CRASH,
    SUBMISSION_SCORE_ZERO_PASS,
)
from utils.logger import get_logger

log = get_logger("analysis.capability_engine")


# ─────────────────────────────────────────────
# Output contract
# ─────────────────────────────────────────────

@dataclass
class CapabilityUpdateResult:
    student_id:     str
    updates:        dict[str, dict]   # concept -> {old_score, new_score, weight_used}
    submission_score: float           # the SubmissionScore value derived from execution result


# ─────────────────────────────────────────────
# SubmissionScore mapping
# ─────────────────────────────────────────────

def compute_submission_score(
    pass_rate: float,
    compiled: bool,
    timeout: bool,
    runtime_error: bool,
) -> float:
    """
    Maps execution result to a scalar SubmissionScore used in the EMA update.

    Priority (highest to lowest):
        timeout or runtime crash → 0.1
        not compiled (syntax)    → 0.2
        compiled, pass_rate == 0 → 0.3
        compiled, 0 < rate < 0.5 → 0.4
        compiled, rate >= 0.5    → 0.6
        pass_rate == 1.0         → 1.0
    """
    if timeout or runtime_error:
        return SUBMISSION_SCORE_TIMEOUT_CRASH

    if not compiled:
        return SUBMISSION_SCORE_SYNTAX_ERROR

    if pass_rate == 1.0:
        return SUBMISSION_SCORE_FULL_PASS

    if pass_rate >= 0.5:
        return SUBMISSION_SCORE_PARTIAL_HIGH

    if pass_rate > 0.0:
        return SUBMISSION_SCORE_PARTIAL_LOW

    # compiled and pass_rate == 0
    return SUBMISSION_SCORE_ZERO_PASS


# ─────────────────────────────────────────────
# EMA score update
# ─────────────────────────────────────────────

def _ema_update(old_score: float, submission_score: float, weight: float) -> float:
    """
    NewScore = (1 - weight) * OldScore + weight * SubmissionScore
    Clamped to [SCORE_MIN, SCORE_MAX] = [0.0, 1.0].
    """
    new_score = (1.0 - weight) * old_score + weight * submission_score
    return max(SCORE_MIN, min(SCORE_MAX, new_score))


# ─────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────

def get_capability_score(student_id: str, concept: str, db: Session) -> float:
    """
    Fetches the current capability score for a (student, concept) pair.
    Returns INITIAL_SCORE (0.5) if no record exists yet.
    """
    record: Optional[CapabilityScore] = (
        db.query(CapabilityScore)
        .filter(
            CapabilityScore.student_id == student_id,
            CapabilityScore.concept == concept,
        )
        .first()
    )
    return record.score if record else INITIAL_SCORE


def _upsert_score(student_id: str, concept: str, new_score: float, db: Session) -> None:
    """
    Insert or update the CapabilityScore row for (student_id, concept).
    Uses a simple select-then-update pattern safe for SQLite.
    """
    record: Optional[CapabilityScore] = (
        db.query(CapabilityScore)
        .filter(
            CapabilityScore.student_id == student_id,
            CapabilityScore.concept == concept,
        )
        .first()
    )
    if record:
        record.score      = new_score
        record.updated_at = datetime.now(timezone.utc)
    else:
        db.add(CapabilityScore(
            student_id=student_id,
            concept=concept,
            score=new_score,
            updated_at=datetime.now(timezone.utc),
        ))


# ─────────────────────────────────────────────
# Public interface
# ─────────────────────────────────────────────

def update_capability_scores(
    student_id:     str,
    concept_tags:   list[str],
    error_type:     str,
    pass_rate:      float,
    compiled:       bool,
    timeout:        bool,
    runtime_error:  bool,
    db:             Session,
) -> CapabilityUpdateResult:
    """
    Updates EMA capability scores for all concept_tags touched by this submission.

    Algorithm per concept:
        1. Look up weight = CONCEPT_WEIGHTS[error_type].get(concept, EMA_DEFAULT_WEIGHT)
        2. Fetch old_score from DB (default INITIAL_SCORE=0.5 if new)
        3. new_score = EMA_update(old_score, submission_score, weight)
        4. Clamp to [0.0, 1.0]
        5. Upsert to capability_scores table

    INVARIANT: This function NEVER reads or writes the difficulty_signal from Brain A.
               difficulty_signal only biases question routing, never capability scores.
    """
    submission_score = compute_submission_score(
        pass_rate=pass_rate,
        compiled=compiled,
        timeout=timeout,
        runtime_error=runtime_error,
    )

    # Normalise error_type — fall back to 'none' if unrecognised
    resolved_error_type = error_type if error_type in CONCEPT_WEIGHTS else "none"
    weight_map = CONCEPT_WEIGHTS[resolved_error_type]

    updates: dict[str, dict] = {}

    for concept in concept_tags:
        weight    = weight_map.get(concept, EMA_DEFAULT_WEIGHT)
        old_score = get_capability_score(student_id, concept, db)
        new_score = _ema_update(old_score, submission_score, weight)

        _upsert_score(student_id, concept, new_score, db)

        updates[concept] = {
            "old_score":    round(old_score, 4),
            "new_score":    round(new_score, 4),
            "weight_used":  weight,
        }

        log.info(
            "capability_score_updated",
            student_id=student_id,
            concept=concept,
            old_score=round(old_score, 4),
            new_score=round(new_score, 4),
            weight=weight,
            submission_score=submission_score,
            error_type=resolved_error_type,
        )

    return CapabilityUpdateResult(
        student_id=student_id,
        updates=updates,
        submission_score=submission_score,
    )


# ─────────────────────────────────────────────
# Bulk read — used by faculty dashboard and question selector
# ─────────────────────────────────────────────

def get_all_capability_scores(student_id: str, db: Session) -> dict[str, float]:
    """
    Returns {concept: score} for all concepts the student has touched.
    Concepts not yet encountered are absent (caller uses INITIAL_SCORE as default).
    """
    records: list[CapabilityScore] = (
        db.query(CapabilityScore)
        .filter(CapabilityScore.student_id == student_id)
        .all()
    )
    return {r.concept: r.score for r in records}


def get_weakest_concept(student_id: str, db: Session) -> Optional[str]:
    """
    Returns the concept with the lowest capability score for the student.
    Returns None if the student has no scored concepts yet.
    Used by escalation.py to detect conceptual gaps.
    """
    record: Optional[CapabilityScore] = (
        db.query(CapabilityScore)
        .filter(CapabilityScore.student_id == student_id)
        .order_by(CapabilityScore.score.asc())
        .first()
    )
    return record.concept if record else None


# ─────────────────────────────────────────────
# Single-concept wrapper — used by routes_submit.py
# ─────────────────────────────────────────────

@dataclass
class CapabilityUpdate:
    """Simplified result for single-concept update used by routes_submit.py."""
    concept:    str
    old_score:  float
    new_score:  float


def update_capability(
    student_id:     str,
    concept:        str,
    pass_rate:      float,
    compiled:       bool,
    timeout:        bool,
    runtime_error:  bool,
    error_type:     str,
    db:             Session,
) -> CapabilityUpdate:
    """
    Single-concept capability update.
    Wraps update_capability_scores for the routes_submit.py call pattern.
    Returns CapabilityUpdate with concept, old_score, new_score.
    """
    result = update_capability_scores(
        student_id=student_id,
        concept_tags=[concept],
        error_type=error_type,
        pass_rate=pass_rate,
        compiled=compiled,
        timeout=timeout,
        runtime_error=runtime_error,
        db=db,
    )

    if concept in result.updates:
        return CapabilityUpdate(
            concept=concept,
            old_score=result.updates[concept]["old_score"],
            new_score=result.updates[concept]["new_score"],
        )
    else:
        # Shouldn't happen, but safe fallback
        score = get_capability_score(student_id, concept, db)
        return CapabilityUpdate(
            concept=concept,
            old_score=score,
            new_score=score,
        )

