# api/routes_student.py
# AdaptLab — GET /student/{student_id}/profile and GET /student/{student_id}/history
# Imports from: database/db.py, database/models.py,
#               ai/escalation.py, schemas/capability.py,
#               schemas/submission.py, utils/logger.py

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ai.escalation import get_escalation_count
from database.db import get_db
from database.models import CapabilityScore, Problem, Student, Submission
from schemas.capability import (
    CapabilityProfileResponse,
    ConceptScoreSchema,
    ZoneSchema,
)
from schemas.submission import (
    SubmissionHistoryItem,
    SubmissionHistoryResponse,
)
from utils.logger import get_logger

router = APIRouter(tags=["student"])
log    = get_logger("api.routes_student")


# ─────────────────────────────────────────────
# Zone classification — mirrors question_selector thresholds
# ─────────────────────────────────────────────

def _classify_zone(score: float) -> tuple[int, str]:
    """
    Returns (zone_int, zone_label) for a capability score.
    Mirrors exact thresholds from spec Section 4.3.
    """
    if score < 0.40:
        return 0, "too_difficult"
    elif score < 0.55:
        return 1, "easy"
    elif score < 0.75:
        return 2, "learning_zone"
    else:
        return 3, "mastery"


def _get_student_or_404(student_id: str, db: Session) -> Student:
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(
            status_code=404,
            detail=f"Student '{student_id}' not found.",
        )
    return student


# ─────────────────────────────────────────────
# POST /student/register
# ─────────────────────────────────────────────

from pydantic import BaseModel, Field


class StudentRegisterRequest(BaseModel):
    student_id: str = Field(..., min_length=1, max_length=64)
    name:       str = Field(..., min_length=1, max_length=200)
    email:      str = Field(..., min_length=3, max_length=200)


@router.post(
    "/student/register",
    summary="Register a new student",
)
def register_student(
    body: StudentRegisterRequest,
    db:   Session = Depends(get_db),
) -> dict:
    """Create a new student. Returns 409 if student_id already exists."""
    existing = db.query(Student).filter(Student.student_id == body.student_id).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Student '{body.student_id}' already exists.")

    student = Student(
        student_id=body.student_id,
        name=body.name,
        email=body.email,
    )
    db.add(student)
    db.commit()

    log.info("student_registered", student_id=body.student_id)
    return {"student_id": body.student_id, "name": body.name, "registered": True}


# ─────────────────────────────────────────────
# GET /student/{student_id}/profile
# ─────────────────────────────────────────────

@router.get(
    "/student/{student_id}/profile",
    response_model=CapabilityProfileResponse,
    summary="Get full capability profile for a student",
)
def get_student_profile(
    student_id: str,
    db:         Session = Depends(get_db),
) -> CapabilityProfileResponse:
    """
    Returns the student's complete capability snapshot:
    - All concept EMA scores with zone classification
    - Weakest and strongest concepts
    - Mean score across all seen concepts
    - Total submissions and escalations
    """
    log.info("get_student_profile", student_id=student_id)

    student = _get_student_or_404(student_id, db)

    # Fetch all capability scores for this student
    cap_rows: list[CapabilityScore] = (
        db.query(CapabilityScore)
        .filter(CapabilityScore.student_id == student_id)
        .order_by(CapabilityScore.concept)
        .all()
    )

    # Build score and zone schemas
    scores: list[ConceptScoreSchema] = []
    zones:  list[ZoneSchema]         = []

    for row in cap_rows:
        scores.append(ConceptScoreSchema(
            concept=row.concept,
            score=round(row.score, 4),
            updated_at=row.updated_at.isoformat() if row.updated_at else None,
        ))
        zone_int, zone_label = _classify_zone(row.score)
        zones.append(ZoneSchema(
            concept=row.concept,
            score=round(row.score, 4),
            zone=zone_int,
            zone_label=zone_label,
        ))

    # Derived stats
    all_scores = [row.score for row in cap_rows]
    mean_score  = round(sum(all_scores) / len(all_scores), 4) if all_scores else None

    weakest_concept:  Optional[str] = None
    strongest_concept: Optional[str] = None
    if cap_rows:
        weakest_row  = min(cap_rows, key=lambda r: r.score)
        strongest_row = max(cap_rows, key=lambda r: r.score)
        weakest_concept   = weakest_row.concept
        strongest_concept = strongest_row.concept

    total_submissions: int = (
        db.query(Submission)
        .filter(Submission.student_id == student_id)
        .count()
    )

    total_escalations: int = get_escalation_count(student_id, db)

    log.info(
        "student_profile_built",
        student_id=student_id,
        concepts_seen=len(cap_rows),
        mean_score=mean_score,
        total_submissions=total_submissions,
    )

    return CapabilityProfileResponse(
        student_id=student_id,
        student_name=student.name,
        total_submissions=total_submissions,
        total_escalations=total_escalations,
        scores=scores,
        zones=zones,
        weakest_concept=weakest_concept,
        strongest_concept=strongest_concept,
        mean_score=mean_score,
        concepts_seen=len(cap_rows),
    )


# ─────────────────────────────────────────────
# GET /student/{student_id}/history
# ─────────────────────────────────────────────

@router.get(
    "/student/{student_id}/history",
    response_model=SubmissionHistoryResponse,
    summary="Get submission history for a student",
)
def get_student_history(
    student_id: str,
    limit:  int = Query(default=50, ge=1, le=200,
                        description="Max number of submissions to return"),
    offset: int = Query(default=0,  ge=0,
                        description="Pagination offset"),
    db: Session = Depends(get_db),
) -> SubmissionHistoryResponse:
    """
    Returns paginated submission history for a student, newest first.
    Includes pass_rate, error_type, escalation flag, and gaming flag
    for each submission. Problem title is joined in for display.
    """
    log.info(
        "get_student_history",
        student_id=student_id,
        limit=limit,
        offset=offset,
    )

    # Verify student exists
    _get_student_or_404(student_id, db)

    # Total count for pagination metadata
    total: int = (
        db.query(Submission)
        .filter(Submission.student_id == student_id)
        .count()
    )

    # Fetch paginated submissions — newest first
    rows: list[Submission] = (
        db.query(Submission)
        .filter(Submission.student_id == student_id)
        .order_by(Submission.submitted_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Bulk fetch problem titles to avoid N+1
    problem_ids = list({row.problem_id for row in rows})
    problem_title_map: dict[str, str] = {}
    if problem_ids:
        problem_rows = (
            db.query(Problem.problem_id, Problem.title)
            .filter(Problem.problem_id.in_(problem_ids))
            .all()
        )
        problem_title_map = {p.problem_id: p.title for p in problem_rows}

    items: list[SubmissionHistoryItem] = []
    for row in rows:
        items.append(SubmissionHistoryItem(
            submission_id=row.submission_id,
            problem_id=row.problem_id,
            problem_title=problem_title_map.get(row.problem_id),
            pass_rate=round(row.pass_rate, 4),
            compiled=row.compiled if row.compiled is not None else False,
            error_type=row.error_type,
            escalated=row.escalated if row.escalated is not None else False,
            gaming_flagged=row.gaming_flagged if row.gaming_flagged is not None else False,
            submitted_at=row.submitted_at.isoformat() if row.submitted_at else "",
        ))

    log.info(
        "student_history_returned",
        student_id=student_id,
        returned=len(items),
        total=total,
    )

    return SubmissionHistoryResponse(
        student_id=student_id,
        total=total,
        submissions=items,
    )
