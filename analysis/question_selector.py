# analysis/question_selector.py
# AdaptLab — Zone-based + Gaussian question routing.
# No LLM involved. Pure deterministic rule engine.
# Imports from: database/db.py, database/models.py, utils/constants.py, utils/logger.py

import json
import math
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from database.models import Problem, Submission
from utils.constants import (
    BAND_MAX,
    BAND_MIN,
    BAND_OFFSET,
    CONCEPT_PREREQUISITES,
    DIFFICULTY_EASY,
    DIFFICULTY_HARD,
    DIFFICULTY_MEDIUM,
    GAUSSIAN_MU,
    GAUSSIAN_SIGMA,
    INITIAL_SCORE,
    USE_GAUSSIAN,
    ZONE_EASY_MAX,
    ZONE_MEDIUM_MAX,
    ZONE_TOO_DIFFICULT,
)
from utils.logger import get_logger

log = get_logger("analysis.question_selector")


# ─────────────────────────────────────────────
# Output contract
# ─────────────────────────────────────────────

@dataclass
class SelectionResult:
    problem_id:     Optional[str]   # None if no suitable problem found
    problem:        Optional[Problem]
    concept:        str
    difficulty:     str
    band:           int
    zone:           int
    band_offset:    int
    selection_mode: str             # 'gaussian' | 'zone_based'
    fallback_used:  bool


# ─────────────────────────────────────────────
# 4.2 — Gaussian Utility (Socratic-Zero, Wang et al. 2025, Eq. 6)
# ─────────────────────────────────────────────

def compute_gaussian_utility(
    student_score: float,
    mu: float = GAUSSIAN_MU,
    sigma: float = GAUSSIAN_SIGMA,
) -> float:
    """
    U(q | pi_s) = exp( -(s_q - mu)^2 / (2 * sigma^2) )

    Returns:
        1.0  when student_score == 0.5  (perfect challenge level)
        0.61 when student_score == 0.7  (slightly too easy)
        0.61 when student_score == 0.3  (slightly too hard)
        0.14 when student_score == 0.9  (mastered — low utility)
        0.14 when student_score == 0.1  (far too hard — low utility)
    """
    return math.exp(-((student_score - mu) ** 2) / (2.0 * sigma ** 2))


# ─────────────────────────────────────────────
# 4.3 — Zone classification
# ─────────────────────────────────────────────

def classify_zone(score: float) -> int:
    """
    Maps a capability score to a zone integer:
        score < 0.40  → 0  (Too Difficult — serve prerequisite)
        score < 0.55  → 1  (Easy band)
        score < 0.75  → 2  (Medium band — Learning Zone sweet spot)
        score >= 0.75 → 3  (Hard band — approaching mastery)
    """
    if score < ZONE_TOO_DIFFICULT:
        return 0
    if score < ZONE_EASY_MAX:
        return 1
    if score < ZONE_MEDIUM_MAX:
        return 2
    return 3


def _band_to_difficulty(band: int) -> str:
    """Maps band integer to difficulty string label."""
    return {
        0: DIFFICULTY_EASY,    # prerequisite concept, easy
        1: DIFFICULTY_EASY,
        2: DIFFICULTY_MEDIUM,
        3: DIFFICULTY_HARD,
    }[band]


def get_prerequisite(concept: str) -> str:
    """
    Returns the prerequisite concept for a given concept.
    Falls back to 'variables' (root) if concept not in graph.
    """
    return CONCEPT_PREREQUISITES.get(concept, "variables")


# ─────────────────────────────────────────────
# Already-seen problem filter
# ─────────────────────────────────────────────

def _get_seen_problem_ids(student_id: str, db: Session) -> set[str]:
    """
    Returns the set of problem_ids this student has already attempted.
    INVARIANT: Same problem_id is NEVER served twice to the same student.
    """
    rows = (
        db.query(Submission.problem_id)
        .filter(Submission.student_id == student_id)
        .distinct()
        .all()
    )
    return {row[0] for row in rows}


# ─────────────────────────────────────────────
# DB problem fetcher
# ─────────────────────────────────────────────

def _fetch_problem(
    concept: str,
    difficulty: str,
    seen_ids: set[str],
    db: Session,
) -> Optional[Problem]:
    """
    Fetches a validated, unseen problem matching concept + difficulty.
    concept match: problem's concept_tags JSON list contains the concept.
    Ordered by difficulty_score ascending (easiest within band first).
    """
    candidates: list[Problem] = (
        db.query(Problem)
        .filter(
            Problem.difficulty == difficulty,
            Problem.validated == True,
            Problem.primary_concept == concept,
        )
        .order_by(Problem.difficulty_score.asc())
        .all()
    )

    for p in candidates:
        if p.problem_id not in seen_ids:
            return p

    # Fallback: try matching via concept_tags (broader match)
    candidates_broad: list[Problem] = (
        db.query(Problem)
        .filter(
            Problem.difficulty == difficulty,
            Problem.validated == True,
        )
        .order_by(Problem.difficulty_score.asc())
        .all()
    )

    for p in candidates_broad:
        if p.problem_id not in seen_ids:
            try:
                tags = json.loads(p.concept_tags)
                if concept in tags:
                    return p
            except (json.JSONDecodeError, TypeError):
                continue

    return None


# ─────────────────────────────────────────────
# Zone-based selector (prototype mode)
# ─────────────────────────────────────────────

def _select_zone_based(
    student_id:       str,
    concept:          str,
    student_score:    float,
    difficulty_signal: str,
    seen_ids:         set[str],
    db:               Session,
) -> SelectionResult:
    """
    Zone routing with Brain A bias offset.

    Step 1: base_zone = classify_zone(student_score)
    Step 2: band_offset from difficulty_signal ('easier'/-1, 'same'/0, 'harder'/+1)
    Step 3: target_band = clamp(base_zone + offset, 0, 3)
    Step 4: if band == 0, use prerequisite concept at easy difficulty
    Step 5: if no problem found at target_band, fall back to band-1
    """
    base_zone   = classify_zone(student_score)
    offset      = BAND_OFFSET.get(difficulty_signal, 0)
    target_band = max(BAND_MIN, min(BAND_MAX, base_zone + offset))

    log.info(
        "zone_routing",
        student_id=student_id,
        concept=concept,
        score=student_score,
        base_zone=base_zone,
        difficulty_signal=difficulty_signal,
        band_offset=offset,
        target_band=target_band,
    )

    fallback_used = False

    for band in _band_fallback_sequence(target_band):
        if band == 0:
            fetch_concept    = get_prerequisite(concept)
            fetch_difficulty = DIFFICULTY_EASY
        else:
            fetch_concept    = concept
            fetch_difficulty = _band_to_difficulty(band)

        problem = _fetch_problem(fetch_concept, fetch_difficulty, seen_ids, db)

        if problem:
            if band != target_band:
                fallback_used = True
            log.info(
                "problem_selected",
                student_id=student_id,
                problem_id=problem.problem_id,
                concept=fetch_concept,
                difficulty=fetch_difficulty,
                band=band,
                fallback=fallback_used,
            )
            return SelectionResult(
                problem_id=problem.problem_id,
                problem=problem,
                concept=fetch_concept,
                difficulty=fetch_difficulty,
                band=band,
                zone=base_zone,
                band_offset=offset,
                selection_mode="zone_based",
                fallback_used=fallback_used,
            )

    log.warning(
        "no_problem_found",
        student_id=student_id,
        concept=concept,
        target_band=target_band,
    )
    return SelectionResult(
        problem_id=None,
        problem=None,
        concept=concept,
        difficulty=_band_to_difficulty(target_band),
        band=target_band,
        zone=base_zone,
        band_offset=offset,
        selection_mode="zone_based",
        fallback_used=True,
    )


def _band_fallback_sequence(target_band: int) -> list[int]:
    """
    Returns bands to try in order: target first, then fall back by -1 each step.
    INVARIANT: If no problem found in target band, fall back to band-1.
    e.g. target=3 → [3, 2, 1, 0]
         target=1 → [1, 0]
         target=0 → [0]
    """
    return list(range(target_band, BAND_MIN - 1, -1))


# ─────────────────────────────────────────────
# Gaussian selector (full version)
# ─────────────────────────────────────────────

def _select_gaussian(
    student_id:    str,
    concept:       str,
    seen_ids:      set[str],
    db:            Session,
) -> SelectionResult:
    """
    Full Gaussian selection: scores every available problem by
    U(q | pi_s) and returns the one with highest utility.

    The student's capability score for the problem's primary_concept
    is used as s_q in the utility function.
    """
    from analysis.capability_engine import get_capability_score

    all_problems: list[Problem] = (
        db.query(Problem)
        .filter(
            Problem.validated == True,
            Problem.primary_concept == concept,
        )
        .all()
    )

    best_problem:  Optional[Problem] = None
    best_utility:  float = -1.0
    best_difficulty: str = DIFFICULTY_MEDIUM

    for p in all_problems:
        if p.problem_id in seen_ids:
            continue
        s_q     = get_capability_score(student_id, p.primary_concept, db)
        utility = compute_gaussian_utility(s_q)
        if utility > best_utility:
            best_utility   = utility
            best_problem   = p
            best_difficulty = p.difficulty

    if best_problem:
        log.info(
            "gaussian_problem_selected",
            student_id=student_id,
            problem_id=best_problem.problem_id,
            utility=round(best_utility, 4),
        )
        return SelectionResult(
            problem_id=best_problem.problem_id,
            problem=best_problem,
            concept=best_problem.primary_concept,
            difficulty=best_difficulty,
            band=-1,           # N/A for Gaussian mode
            zone=-1,           # N/A for Gaussian mode
            band_offset=0,
            selection_mode="gaussian",
            fallback_used=False,
        )

    log.warning("gaussian_no_problem_found", student_id=student_id, concept=concept)
    return SelectionResult(
        problem_id=None,
        problem=None,
        concept=concept,
        difficulty=DIFFICULTY_MEDIUM,
        band=-1,
        zone=-1,
        band_offset=0,
        selection_mode="gaussian",
        fallback_used=True,
    )


# ─────────────────────────────────────────────
# Public interface
# ─────────────────────────────────────────────

def select_next_problem(
    student_id:        str,
    concept:           str,
    student_score:     Optional[float],
    difficulty_signal: str,
    db:                Session,
) -> SelectionResult:
    """
    Main entry point. Dispatches to zone-based or Gaussian selector
    based on the USE_GAUSSIAN flag in constants.py.

    Args:
        student_id:        student UUID
        concept:           primary concept to target
        student_score:     capability score for this concept (None → use INITIAL_SCORE)
        difficulty_signal: Brain A signal — 'easier' | 'same' | 'harder'
        db:                SQLAlchemy session

    Returns:
        SelectionResult with the chosen problem (or problem_id=None if bank exhausted)

    INVARIANTS enforced here:
        1. difficulty_signal NEVER writes to capability_scores table
        2. Same problem_id NEVER served twice to same student
        3. If no problem in target band → fall back to band-1
    """
    score = student_score if student_score is not None else INITIAL_SCORE
    seen_ids = _get_seen_problem_ids(student_id, db)

    if USE_GAUSSIAN:
        return _select_gaussian(
            student_id=student_id,
            concept=concept,
            seen_ids=seen_ids,
            db=db,
        )
    else:
        return _select_zone_based(
            student_id=student_id,
            concept=concept,
            student_score=score,
            difficulty_signal=difficulty_signal,
            seen_ids=seen_ids,
            db=db,
        )


# ─────────────────────────────────────────────
# Convenience wrapper — used by routes_submit.py and routes_problems.py
# ─────────────────────────────────────────────

def get_next_problem(
    student_id:       str,
    concept:          str,
    seen_problem_ids: list[str],
    db:               Session,
    difficulty_signal: str = "same",
) -> Optional[SelectionResult]:
    """
    Wrapper around select_next_problem that:
    1. Fetches the student's current capability score from DB
    2. Uses a default difficulty_signal of 'same'
    3. Returns SelectionResult (or None if no problem available)

    This is the interface used by routes_submit.py and routes_problems.py.
    """
    from analysis.capability_engine import get_capability_score

    student_score = get_capability_score(student_id, concept, db)

    result = select_next_problem(
        student_id=student_id,
        concept=concept,
        student_score=student_score,
        difficulty_signal=difficulty_signal,
        db=db,
    )

    # If problem_id is None, no suitable problem was found
    if result.problem_id is None:
        return None

    return result
