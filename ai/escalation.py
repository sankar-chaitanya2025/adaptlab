# ai/escalation.py
# AdaptLab — Rule engine that decides if Brain B should run.
# Pure deterministic logic. No LLM involved.
# Returns (should_escalate: bool, reason: str | None)
# Imports from: database/db.py, database/models.py, utils/constants.py, utils/logger.py

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from database.models import CapabilityScore, EscalationLog, Problem, Submission
from utils.constants import ESCALATION_LOW_CAP, ESCALATION_STREAK
from utils.logger import get_logger

log = get_logger("ai.escalation")


# ─────────────────────────────────────────────
# Output contract
# ─────────────────────────────────────────────

@dataclass
class EscalationResult:
    should_escalate:    bool
    reason:             Optional[str]   # 'student_request' | 'streak' | 'low_capability' |
                                        # 'conceptual_gap' | None


# ─────────────────────────────────────────────
# Rule helpers
# ─────────────────────────────────────────────

def _count_consecutive_failures(
    student_id: str,
    concept: str,
    db: Session,
) -> int:
    """
    Counts the current streak of consecutive failed submissions
    for this student on any problem with the same primary_concept.

    A failure = pass_rate < 1.0.
    Streak resets as soon as a pass_rate == 1.0 is found when scanning
    backward through recent submissions.
    """
    recent: list[Submission] = (
        db.query(Submission)
        .join(Problem, Submission.problem_id == Problem.problem_id)
        .filter(
            Submission.student_id == student_id,
            Problem.primary_concept == concept,
        )
        .order_by(Submission.submitted_at.desc())
        .limit(ESCALATION_STREAK + 5)   # fetch a few extra for safety
        .all()
    )

    streak = 0
    for sub in recent:
        if sub.pass_rate < 1.0:
            streak += 1
        else:
            break   # streak resets on first full pass

    return streak


def _get_capability_score(
    student_id: str,
    concept: str,
    db: Session,
) -> float:
    """
    Fetches the student's current capability score for the given concept.
    Returns INITIAL_SCORE (0.5) if no record exists.
    """
    from utils.constants import INITIAL_SCORE

    record: Optional[CapabilityScore] = (
        db.query(CapabilityScore)
        .filter(
            CapabilityScore.student_id == student_id,
            CapabilityScore.concept == concept,
        )
        .first()
    )
    return record.score if record else INITIAL_SCORE


def _log_escalation(
    student_id:     str,
    problem_id:     str,
    submission_id:  str,
    reason:         str,
    db:             Session,
) -> None:
    """
    Writes a row to EscalationLog.
    Called for ALL escalations regardless of reason — spec requirement.
    """
    entry = EscalationLog(
        log_id=str(uuid.uuid4()),
        student_id=student_id,
        problem_id=problem_id,
        submission_id=submission_id,
        reason=reason,
        resolved=False,
        logged_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    db.flush()

    log.info(
        "escalation_logged",
        student_id=student_id,
        problem_id=problem_id,
        submission_id=submission_id,
        reason=reason,
    )


# ─────────────────────────────────────────────
# Public interface
# ─────────────────────────────────────────────

def check_escalation(
    student_id:             str,
    problem_id:             str,
    submission_id:          str,
    concept:                str,
    pass_rate:              float,
    compiled:               bool,
    error_type:             str,
    deep_explain_requested: bool,
    db:                     Session,
) -> EscalationResult:
    """
    Evaluates all escalation rules in priority order and returns
    the first match. Logs ALL positive results to EscalationLog.

    Rules (spec Section 7.6, checked in this exact order):
        1. student_request  — student explicitly asked for deep explanation
        2. streak           — consecutive failures >= ESCALATION_STREAK (3)
        3. low_capability   — capability score < ESCALATION_LOW_CAP (0.40)
        4. conceptual_gap   — compiled, pass_rate < 0.5, error not surface-level

    Returns (False, None) if no rule triggers.
    """

    # ── Rule 1: Student Request ───────────────
    if deep_explain_requested:
        reason = "student_request"
        _log_escalation(student_id, problem_id, submission_id, reason, db)
        log.info("escalation_triggered", rule=reason, student_id=student_id)
        return EscalationResult(should_escalate=True, reason=reason)

    # ── Rule 2: Failure Streak ────────────────
    streak = _count_consecutive_failures(student_id, concept, db)
    if streak >= ESCALATION_STREAK:
        reason = "streak"
        _log_escalation(student_id, problem_id, submission_id, reason, db)
        log.info(
            "escalation_triggered",
            rule=reason,
            student_id=student_id,
            streak=streak,
        )
        return EscalationResult(should_escalate=True, reason=reason)

    # ── Rule 3: Low Capability Score ─────────
    score = _get_capability_score(student_id, concept, db)
    if score < ESCALATION_LOW_CAP:
        reason = "low_capability"
        _log_escalation(student_id, problem_id, submission_id, reason, db)
        log.info(
            "escalation_triggered",
            rule=reason,
            student_id=student_id,
            score=score,
        )
        return EscalationResult(should_escalate=True, reason=reason)

    # ── Rule 4: Conceptual Gap ────────────────
    # Compiled code that still fails more than half the tests,
    # and the error is not a simple surface-level fix.
    _SURFACE_ERRORS = {"syntax_error", "off_by_one"}
    if compiled and pass_rate < 0.5 and error_type not in _SURFACE_ERRORS:
        reason = "conceptual_gap"
        _log_escalation(student_id, problem_id, submission_id, reason, db)
        log.info(
            "escalation_triggered",
            rule=reason,
            student_id=student_id,
            pass_rate=pass_rate,
            error_type=error_type,
        )
        return EscalationResult(should_escalate=True, reason=reason)

    # ── No rule triggered ─────────────────────
    log.info(
        "escalation_not_triggered",
        student_id=student_id,
        streak=streak,
        score=round(score, 3),
        pass_rate=pass_rate,
    )
    return EscalationResult(should_escalate=False, reason=None)


# ─────────────────────────────────────────────
# Utility — mark escalation resolved (used by faculty endpoints)
# ─────────────────────────────────────────────

def resolve_escalation(log_id: str, db: Session) -> bool:
    """
    Marks an EscalationLog entry as resolved.
    Returns True if found and updated, False if not found.
    """
    entry: Optional[EscalationLog] = (
        db.query(EscalationLog)
        .filter(EscalationLog.log_id == log_id)
        .first()
    )
    if not entry:
        return False

    entry.resolved = True
    db.flush()
    log.info("escalation_resolved", log_id=log_id)
    return True


def get_escalation_count(student_id: str, db: Session) -> int:
    """
    Returns total escalation count for a student.
    Used by routes_student.py profile endpoint.
    """
    return (
        db.query(EscalationLog)
        .filter(EscalationLog.student_id == student_id)
        .count()
    )


def get_escalation_rate(db: Session) -> float:
    """
    Returns the fraction of all submissions that triggered escalation.
    Used by faculty dashboard.
    """
    from database.models import Submission as Sub
    total_subs = db.query(Sub).count()
    if total_subs == 0:
        return 0.0
    total_escalations = db.query(EscalationLog).count()
    return round(total_escalations / total_subs, 4)
