# api/routes_problems.py
# AdaptLab — GET /problems/next and GET /problems/{problem_id}
# Imports from: database/db.py, database/models.py,
#               analysis/question_selector.py,
#               schemas/problem.py, utils/logger.py

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from analysis.question_selector import SelectionResult, get_next_problem
from database.db import get_db
from database.models import Problem, Submission
from schemas.problem import (
    NextProblemResponse,
    ProblemDetailResponse,
    ProblemStudentSchema,
    VisibleTestCaseSchema,
)
from utils.logger import get_logger

router = APIRouter(tags=["problems"])
log    = get_logger("api.routes_problems")


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _problem_to_student_schema(problem: Problem) -> ProblemStudentSchema:
    """
    Converts ORM Problem to student-safe schema.
    Hidden test cases are stripped — only visible examples returned.
    """
    all_cases: list[dict] = json.loads(problem.test_cases)
    visible_cases = [
        VisibleTestCaseSchema(input=tc["input"], output=tc["output"])
        for tc in all_cases
        if not tc.get("hidden", False)
    ]
    total_hidden = sum(1 for tc in all_cases if tc.get("hidden", False))

    concept_tags: list[str] = json.loads(problem.concept_tags)

    return ProblemStudentSchema(
        problem_id=problem.problem_id,
        title=problem.title,
        statement=problem.statement,
        concept_tags=concept_tags,
        primary_concept=problem.primary_concept,
        difficulty=problem.difficulty,
        expected_complexity=problem.expected_complexity,
        example_cases=visible_cases,
        total_test_cases=len(all_cases),
        hidden_test_count=total_hidden,
    )


def _get_problem_or_404(problem_id: str, db: Session) -> Problem:
    """Fetches a validated, active problem from DB or raises 404."""
    problem: Optional[Problem] = (
        db.query(Problem)
        .filter(
            Problem.problem_id == problem_id,
            Problem.validated  == True,
        )
        .first()
    )
    if not problem:
        raise HTTPException(
            status_code=404,
            detail=f"Problem '{problem_id}' not found or not validated.",
        )
    return problem


# ─────────────────────────────────────────────
# GET /problems/next
# ─────────────────────────────────────────────

@router.get(
    "/problems/next",
    response_model=NextProblemResponse,
    summary="Get next adaptive problem for a student",
)
def get_next_adaptive_problem(
    student_id: str = Query(..., min_length=1, max_length=64,
                            description="Student identifier"),
    concept:    str = Query(..., min_length=1, max_length=64,
                            description="Primary concept to practice"),
    db:         Session = Depends(get_db),
) -> NextProblemResponse:
    """
    Selects the next problem for this student using zone-based routing
    (or Gaussian selection if USE_GAUSSIAN=True in constants).

    Invariants enforced here:
    1. Never serve the same problem_id twice to the same student.
    2. Returned test cases are VISIBLE ONLY — hidden content stripped.
    3. If no problem available: returns HTTP 404 with informative message.
    """
    log.info(
        "next_problem_request",
        student_id=student_id,
        concept=concept,
    )

    # Fetch IDs of problems already seen by this student
    seen_ids: list[str] = [
        row.problem_id
        for row in db.query(Submission.problem_id)
                     .filter(Submission.student_id == student_id)
                     .distinct()
                     .all()
    ]

    result: Optional[SelectionResult] = get_next_problem(
        student_id=student_id,
        concept=concept,
        seen_problem_ids=seen_ids,
        db=db,
    )

    if result is None or result.problem_id is None:
        log.warning(
            "next_problem_not_found",
            student_id=student_id,
            concept=concept,
        )
        raise HTTPException(
            status_code=404,
            detail=(
                f"No unseen problems available for concept '{concept}'. "
                "All problems in this concept have been attempted, "
                "or the problem bank needs more entries for this concept."
            ),
        )

    problem = _get_problem_or_404(result.problem_id, db)
    student_schema = _problem_to_student_schema(problem)

    log.info(
        "next_problem_selected",
        student_id=student_id,
        problem_id=result.problem_id,
        band=result.band,
        zone=result.zone,
        selection_mode=result.selection_mode,
        fallback_used=result.fallback_used,
    )

    return NextProblemResponse(
        problem=student_schema,
        selection_mode=result.selection_mode,
        band=result.band,
        zone=result.zone,
        band_offset=result.band_offset,
        fallback_used=result.fallback_used,
    )


# ─────────────────────────────────────────────
# GET /problems/{problem_id}
# ─────────────────────────────────────────────

@router.get(
    "/problems/{problem_id}",
    response_model=ProblemDetailResponse,
    summary="Get a specific problem by ID (student-safe view)",
)
def get_problem_by_id(
    problem_id: str,
    db:         Session = Depends(get_db),
) -> ProblemDetailResponse:
    """
    Returns a student-safe view of the problem.
    Hidden test cases are stripped — only visible example cases included.
    Returns 404 if problem doesn't exist or is not validated.
    """
    log.info("get_problem_by_id", problem_id=problem_id)

    problem = _get_problem_or_404(problem_id, db)
    student_schema = _problem_to_student_schema(problem)

    return ProblemDetailResponse(problem=student_schema)
