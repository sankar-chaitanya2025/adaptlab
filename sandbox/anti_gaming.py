# sandbox/anti_gaming.py
# AdaptLab — Hardcoding detection + rapid resubmit detection.
# Imports from: database/db.py, utils/constants.py, utils/logger.py

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from database.models import Submission
from utils.constants import (
    ANTI_GAME_COOLDOWN_S,
    ANTI_GAME_DISTINCT_MIN,
    ANTI_GAME_GAP,
    ANTI_GAME_HIDDEN_THRESH,
    ANTI_GAME_SCORE_CAP,
    ANTI_GAME_SUBMIT_MAX,
    ANTI_GAME_VISIBLE_FULL,
    ANTI_GAME_WINDOW_MIN,
)
from utils.logger import get_logger

log = get_logger("sandbox.anti_gaming")


# ─────────────────────────────────────────────
# In-memory cooldown store
# Maps student_id -> cooldown_expiry (UTC datetime)
# Resets on server restart — acceptable for prototype.
# ─────────────────────────────────────────────

_cooldown_store: dict[str, datetime] = {}


# ─────────────────────────────────────────────
# Output contracts
# ─────────────────────────────────────────────

@dataclass
class HardcodingResult:
    flagged:            bool
    reason:             Optional[str]       # 'visible_only_pass' | 'suspicious_gap' | None
    capped_score:       Optional[float]     # ANTI_GAME_SCORE_CAP if flagged, else None


@dataclass
class RapidResubmitResult:
    flagged:            bool
    reason:             Optional[str]       # 'rapid_resubmit' | None
    cooldown_active:    bool
    cooldown_seconds_remaining: int


# ─────────────────────────────────────────────
# 1. Hardcoding detection (post-execution check)
# ─────────────────────────────────────────────

def check_hardcoding(
    visible_pass_rate: float,
    hidden_pass_rate: Optional[float],
) -> HardcodingResult:
    """
    Detects whether student code is hardcoded against visible test cases.

    Rule 1 — visible_only_pass:
        visible_pass_rate == 1.0 AND hidden_pass_rate < 0.50

    Rule 2 — suspicious_gap:
        (visible_pass_rate - hidden_pass_rate) > ANTI_GAME_GAP (0.40)

    If flagged: cap SubmissionScore at ANTI_GAME_SCORE_CAP (0.3) regardless
    of actual pass_rate. The caller (routes_submit.py) enforces this cap.
    """
    # No hidden tests → cannot evaluate gap; skip check.
    if hidden_pass_rate is None:
        return HardcodingResult(flagged=False, reason=None, capped_score=None)

    flagged = False
    reason: Optional[str] = None

    if visible_pass_rate == ANTI_GAME_VISIBLE_FULL and hidden_pass_rate < ANTI_GAME_HIDDEN_THRESH:
        flagged = True
        reason = "visible_only_pass"

    elif (visible_pass_rate - hidden_pass_rate) > ANTI_GAME_GAP:
        flagged = True
        reason = "suspicious_gap"

    if flagged:
        log.warning(
            "hardcoding_detected",
            reason=reason,
            visible_pass_rate=visible_pass_rate,
            hidden_pass_rate=hidden_pass_rate,
            cap=ANTI_GAME_SCORE_CAP,
        )
        return HardcodingResult(
            flagged=True,
            reason=reason,
            capped_score=ANTI_GAME_SCORE_CAP,
        )

    return HardcodingResult(flagged=False, reason=None, capped_score=None)


# ─────────────────────────────────────────────
# 2. Rapid resubmit detection (pre-execution check)
# ─────────────────────────────────────────────

def check_rapid_resubmit(
    student_id: str,
    problem_id: str,
    current_code: str,
    db: Session,
) -> RapidResubmitResult:
    """
    Detects students who spam-submit without changing their code.

    Condition:
        submissions_in_last_3_minutes >= 5
        AND distinct_code_versions <= 1

    If triggered: apply 60s cooldown and flag.
    If already on cooldown: return flagged immediately without DB query.
    """
    # ── Check existing cooldown first ─────────
    cooldown_result = _check_cooldown(student_id)
    if cooldown_result.cooldown_active:
        log.info(
            "cooldown_active",
            student_id=student_id,
            seconds_remaining=cooldown_result.cooldown_seconds_remaining,
        )
        return cooldown_result

    # ── Query recent submissions ───────────────
    window_start = datetime.now(timezone.utc) - timedelta(minutes=ANTI_GAME_WINDOW_MIN)

    recent: list[Submission] = (
        db.query(Submission)
        .filter(
            Submission.student_id == student_id,
            Submission.problem_id == problem_id,
            Submission.submitted_at >= window_start,
        )
        .order_by(Submission.submitted_at.desc())
        .all()
    )

    submissions_in_window = len(recent)

    if submissions_in_window < ANTI_GAME_SUBMIT_MAX:
        return RapidResubmitResult(
            flagged=False,
            reason=None,
            cooldown_active=False,
            cooldown_seconds_remaining=0,
        )

    # ── Count distinct code versions ──────────
    code_hashes: set[str] = {_hash_code(s.code) for s in recent}
    code_hashes.add(_hash_code(current_code))
    distinct_versions = len(code_hashes)

    if distinct_versions <= ANTI_GAME_DISTINCT_MIN:
        _apply_cooldown(student_id, seconds=ANTI_GAME_COOLDOWN_S)
        log.warning(
            "rapid_resubmit_detected",
            student_id=student_id,
            problem_id=problem_id,
            submissions_in_window=submissions_in_window,
            distinct_versions=distinct_versions,
            cooldown_s=ANTI_GAME_COOLDOWN_S,
        )
        return RapidResubmitResult(
            flagged=True,
            reason="rapid_resubmit",
            cooldown_active=True,
            cooldown_seconds_remaining=ANTI_GAME_COOLDOWN_S,
        )

    return RapidResubmitResult(
        flagged=False,
        reason=None,
        cooldown_active=False,
        cooldown_seconds_remaining=0,
    )


# ─────────────────────────────────────────────
# 3. Cooldown helpers
# ─────────────────────────────────────────────

def _apply_cooldown(student_id: str, seconds: int) -> None:
    """Stores cooldown expiry in the in-memory store."""
    expiry = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    _cooldown_store[student_id] = expiry
    log.info("cooldown_applied", student_id=student_id, expires_at=expiry.isoformat())


def _check_cooldown(student_id: str) -> RapidResubmitResult:
    """Returns a flagged result if the student is still within their cooldown window."""
    expiry = _cooldown_store.get(student_id)
    if expiry is None:
        return RapidResubmitResult(
            flagged=False,
            reason=None,
            cooldown_active=False,
            cooldown_seconds_remaining=0,
        )

    now = datetime.now(timezone.utc)
    if now < expiry:
        remaining = int((expiry - now).total_seconds())
        return RapidResubmitResult(
            flagged=True,
            reason="rapid_resubmit",
            cooldown_active=True,
            cooldown_seconds_remaining=remaining,
        )

    # Cooldown expired — purge it
    del _cooldown_store[student_id]
    return RapidResubmitResult(
        flagged=False,
        reason=None,
        cooldown_active=False,
        cooldown_seconds_remaining=0,
    )


def is_on_cooldown(student_id: str) -> bool:
    """Lightweight public check — used by routes_submit.py before running executor."""
    result = _check_cooldown(student_id)
    return result.cooldown_active


# ─────────────────────────────────────────────
# 4. Utility
# ─────────────────────────────────────────────

def _hash_code(code: str) -> str:
    """
    Returns a stable SHA-256 hash of normalised code.
    Strips leading/trailing whitespace before hashing so that
    purely whitespace-padded resubmits are treated as identical.
    """
    normalised = code.strip()
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


# ─────────────────────────────────────────────
# 5. Unified interface (used by routes_submit.py)
# ─────────────────────────────────────────────

@dataclass
class AntiGamingResult:
    """Combined anti-gaming result wrapping both hardcoding + rapid resubmit."""
    flagged:                    bool
    reason:                     Optional[str]   # 'visible_only_pass' | 'suspicious_gap' | 'rapid_resubmit' | None
    cooldown_active:            bool
    cooldown_seconds_remaining: int
    capped_score:               Optional[float]


def check_anti_gaming(
    student_id:         str,
    current_code:       str,
    db:                 Session,
    problem_id:         str = "",
    visible_pass_rate:  Optional[float] = None,
    hidden_pass_rate:   Optional[float] = None,
) -> AntiGamingResult:
    """
    Unified anti-gaming check used by routes_submit.py.

    Pre-execution call (visible_pass_rate is None):
        Checks rapid resubmit only.

    Post-execution call (visible_pass_rate provided):
        Checks hardcoding detection only.
    """
    # ── Pre-execution: rapid resubmit check ───
    if visible_pass_rate is None:
        rapid = check_rapid_resubmit(
            student_id=student_id,
            problem_id=problem_id,
            current_code=current_code,
            db=db,
        )
        return AntiGamingResult(
            flagged=rapid.flagged,
            reason=rapid.reason,
            cooldown_active=rapid.cooldown_active,
            cooldown_seconds_remaining=rapid.cooldown_seconds_remaining,
            capped_score=None,
        )

    # ── Post-execution: hardcoding check ──────
    hc = check_hardcoding(
        visible_pass_rate=visible_pass_rate,
        hidden_pass_rate=hidden_pass_rate,
    )
    return AntiGamingResult(
        flagged=hc.flagged,
        reason=hc.reason,
        cooldown_active=False,
        cooldown_seconds_remaining=0,
        capped_score=hc.capped_score,
    )

