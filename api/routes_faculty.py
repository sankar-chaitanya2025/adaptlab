# api/routes_faculty.py
# AdaptLab — Faculty endpoints:
#   GET  /faculty/dashboard
#   GET  /faculty/class-overview
#   GET  /faculty/escalations          (unresolved escalation queue)
#   POST /faculty/escalations/{log_id}/resolve
# Imports from: database/db.py, database/models.py,
#               ai/escalation.py, schemas/capability.py, utils/logger.py

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ai.escalation import get_escalation_rate, resolve_escalation
from database.db import get_db
from database.models import (
    CapabilityScore,
    EscalationLog,
    Problem,
    Student,
    Submission,
)
from schemas.capability import (
    ClassOverviewResponse,
    ConceptClassStatsSchema,
    FacultyDashboardResponse,
    StudentSummarySchema,
)
from utils.logger import get_logger

router = APIRouter(tags=["faculty"])
log    = get_logger("api.routes_faculty")


# ─────────────────────────────────────────────
# Zone classifier (mirrors question_selector.py thresholds)
# ─────────────────────────────────────────────

def _zone(score: float) -> int:
    if score < 0.40:   return 0
    elif score < 0.55: return 1
    elif score < 0.75: return 2
    else:              return 3


# ─────────────────────────────────────────────
# GET /faculty/dashboard
# ─────────────────────────────────────────────

@router.get(
    "/faculty/dashboard",
    response_model=FacultyDashboardResponse,
    summary="Faculty dashboard — class-wide stats and concept weak spots",
)
def faculty_dashboard(db: Session = Depends(get_db)) -> FacultyDashboardResponse:
    """
    Returns:
    - Total and active student counts
    - Total submissions platform-wide
    - Escalation rate and gaming flag rate
    - Per-concept class aggregates (mean, min, max, zone distribution)
      sorted by mean_score ASC (weakest concepts first)
    - Count of students in zone 0 (needs intervention)
    - Count of students in learning zone (zones 1+2)
    """
    log.info("faculty_dashboard_request")

    total_students: int = db.query(Student).count()

    # Active = at least one submission
    active_student_ids = [
        row.student_id
        for row in db.query(Submission.student_id).distinct().all()
    ]
    active_students: int = len(active_student_ids)

    total_submissions: int = db.query(Submission).count()

    # Escalation rate
    escalation_rate: float = get_escalation_rate(db)

    # Gaming flag rate
    gaming_flagged_count: int = (
        db.query(Submission)
        .filter(Submission.gaming_flagged == True)
        .count()
    )
    gaming_flag_rate: float = (
        round(gaming_flagged_count / total_submissions, 4)
        if total_submissions > 0 else 0.0
    )

    # ── Per-concept class aggregates ─────────────────────────────────────────
    all_cap_rows: list[CapabilityScore] = db.query(CapabilityScore).all()

    # Group by concept
    concept_map: dict[str, list[float]] = {}
    for row in all_cap_rows:
        concept_map.setdefault(row.concept, []).append(row.score)

    concept_stats: list[ConceptClassStatsSchema] = []
    for concept, scores in concept_map.items():
        n         = len(scores)
        mean_s    = round(sum(scores) / n, 4)
        min_s     = round(min(scores), 4)
        max_s     = round(max(scores), 4)
        zones     = [_zone(s) for s in scores]
        concept_stats.append(ConceptClassStatsSchema(
            concept=concept,
            mean_score=mean_s,
            min_score=min_s,
            max_score=max_s,
            students_seen=n,
            in_zone_0=zones.count(0),
            in_zone_1=zones.count(1),
            in_zone_2=zones.count(2),
            in_zone_3=zones.count(3),
        ))

    # Sort by mean_score ASC — weakest concepts first
    concept_stats.sort(key=lambda x: x.mean_score)

    # ── Students in zone 0 and learning zone ─────────────────────────────────
    # Per student: compute their mean score across all concepts
    student_mean: dict[str, float] = {}
    for row in all_cap_rows:
        bucket = student_mean.setdefault(row.student_id, [])
        if isinstance(bucket, list):
            bucket.append(row.score)

    students_in_zone_0         = 0
    students_in_learning_zone  = 0
    for sid, scores_list in student_mean.items():
        if isinstance(scores_list, list) and scores_list:
            m = sum(scores_list) / len(scores_list)
            z = _zone(m)
            if z == 0:
                students_in_zone_0 += 1
            elif z in (1, 2):
                students_in_learning_zone += 1

    log.info(
        "faculty_dashboard_built",
        total_students=total_students,
        active_students=active_students,
        total_submissions=total_submissions,
        concept_count=len(concept_stats),
    )

    return FacultyDashboardResponse(
        total_students=total_students,
        active_students=active_students,
        total_submissions=total_submissions,
        escalation_rate=escalation_rate,
        gaming_flag_rate=gaming_flag_rate,
        concept_stats=concept_stats,
        students_in_zone_0=students_in_zone_0,
        students_in_learning_zone=students_in_learning_zone,
    )


# ─────────────────────────────────────────────
# GET /faculty/class-overview
# ─────────────────────────────────────────────

@router.get(
    "/faculty/class-overview",
    response_model=ClassOverviewResponse,
    summary="Faculty class overview — per-student ranked summary",
)
def faculty_class_overview(db: Session = Depends(get_db)) -> ClassOverviewResponse:
    """
    Returns all students ranked by mean capability score ASC (weakest first).
    Each row includes: mean_score, weakest/strongest concept,
    total submissions, escalation count, gaming flag count,
    and whether student is in the Learning Zone.
    """
    log.info("faculty_class_overview_request")

    all_students: list[Student] = db.query(Student).all()

    # Build submission counts per student in bulk
    sub_count_rows = (
        db.query(Submission.student_id,
                 db.query(Submission).filter(Submission.student_id == Submission.student_id).count)
        .all()
    )

    # Bulk fetch submission counts
    from sqlalchemy import func
    sub_counts: dict[str, int] = {
        row.student_id: row.total
        for row in db.query(
            Submission.student_id,
            func.count(Submission.submission_id).label("total"),
        )
        .group_by(Submission.student_id)
        .all()
    }

    # Bulk fetch gaming flag counts
    gaming_counts: dict[str, int] = {
        row.student_id: row.total
        for row in db.query(
            Submission.student_id,
            func.count(Submission.submission_id).label("total"),
        )
        .filter(Submission.gaming_flagged == True)
        .group_by(Submission.student_id)
        .all()
    }

    # Bulk fetch escalation counts
    escalation_counts: dict[str, int] = {
        row.student_id: row.total
        for row in db.query(
            EscalationLog.student_id,
            func.count(EscalationLog.log_id).label("total"),
        )
        .group_by(EscalationLog.student_id)
        .all()
    }

    # Bulk fetch capability scores grouped by student
    cap_rows: list[CapabilityScore] = db.query(CapabilityScore).all()
    student_caps: dict[str, list[CapabilityScore]] = {}
    for row in cap_rows:
        student_caps.setdefault(row.student_id, []).append(row)

    summaries: list[StudentSummarySchema] = []
    for student in all_students:
        sid   = student.student_id
        caps  = student_caps.get(sid, [])

        if caps:
            scores            = [r.score for r in caps]
            mean_s            = round(sum(scores) / len(scores), 4)
            weakest_concept   = min(caps, key=lambda r: r.score).concept
            strongest_concept = max(caps, key=lambda r: r.score).concept
        else:
            mean_s            = 0.5   # INITIAL_SCORE — no data yet
            weakest_concept   = None
            strongest_concept = None

        zone              = _zone(mean_s)
        in_learning_zone  = zone in (1, 2)

        summaries.append(StudentSummarySchema(
            student_id=sid,
            student_name=student.name,
            mean_score=mean_s,
            weakest_concept=weakest_concept,
            strongest_concept=strongest_concept,
            total_submissions=sub_counts.get(sid, 0),
            total_escalations=escalation_counts.get(sid, 0),
            gaming_flag_count=gaming_counts.get(sid, 0),
            in_learning_zone=in_learning_zone,
        ))

    # Sort by mean_score ASC — weakest students first for faculty triage
    summaries.sort(key=lambda s: s.mean_score)

    log.info(
        "faculty_class_overview_built",
        total_students=len(summaries),
    )

    return ClassOverviewResponse(
        total_students=len(summaries),
        students=summaries,
    )


# ─────────────────────────────────────────────
# GET /faculty/escalations
# ─────────────────────────────────────────────

@router.get(
    "/faculty/escalations",
    summary="Get all unresolved escalations requiring faculty attention",
)
def get_unresolved_escalations(
    db: Session = Depends(get_db),
) -> dict:
    """
    Returns all unresolved EscalationLog entries.
    Faculty can review these and decide if manual intervention is needed.
    Sorted by logged_at ASC — oldest unresolved first.
    """
    log.info("faculty_escalations_request")

    rows: list[EscalationLog] = (
        db.query(EscalationLog)
        .filter(EscalationLog.resolved == False)
        .order_by(EscalationLog.logged_at.asc())
        .all()
    )

    items = [
        {
            "log_id":        row.log_id,
            "student_id":    row.student_id,
            "problem_id":    row.problem_id,
            "submission_id": row.submission_id,
            "reason":        row.reason,
            "logged_at":     row.logged_at.isoformat() if row.logged_at else None,
        }
        for row in rows
    ]

    log.info("faculty_escalations_returned", count=len(items))

    return {"total": len(items), "escalations": items}


# ─────────────────────────────────────────────
# POST /faculty/escalations/{log_id}/resolve
# ─────────────────────────────────────────────

@router.post(
    "/faculty/escalations/{log_id}/resolve",
    summary="Mark an escalation as resolved",
)
def resolve_escalation_entry(
    log_id: str,
    db:     Session = Depends(get_db),
) -> dict:
    """
    Marks an EscalationLog entry as resolved.
    Returns 404 if log_id not found.
    """
    log.info("faculty_resolve_escalation", log_id=log_id)

    success = resolve_escalation(log_id=log_id, db=db)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Escalation log '{log_id}' not found.",
        )

    db.commit()
    log.info("faculty_escalation_resolved", log_id=log_id)
    return {"log_id": log_id, "resolved": True}
