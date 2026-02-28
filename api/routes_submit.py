# api/routes_submit.py
# AdaptLab — POST /submit. Full 10-step pipeline orchestrator.
# This is the most critical endpoint — coordinates every component.
# Imports from: all modules built so far.

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ai.brain_a import BrainAInput, BrainAOutput, get_feedback
from ai.brain_b import BrainBInput, BrainBOutput, get_deep_explanation
from ai.escalation import EscalationResult, check_escalation
from ai.validator import validate_problem
from analysis.capability_engine import update_capability
from analysis.feature_extractor import extract_features
from analysis.question_selector import SelectionResult, get_next_problem
from database.db import get_db
from database.models import Problem, Student, Submission
from sandbox.anti_gaming import AntiGamingResult, check_anti_gaming
from sandbox.executor import ExecutionResult, run_code
from schemas.problem import ProblemStudentSchema, VisibleTestCaseSchema
from schemas.submission import (
    CapabilityUpdateSchema,
    CooldownResponse,
    DeepExplanationSchema,
    FeedbackSchema,
    NextProblemSchema,
    SubmitRequest,
    SubmitResponse,
    TestCaseResult,
)
from utils.logger import get_logger

router = APIRouter(tags=["submit"])
log    = get_logger("api.routes_submit")


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _get_student_or_404(student_id: str, db: Session) -> Student:
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"Student '{student_id}' not found.")
    return student


def _get_problem_or_404(problem_id: str, db: Session) -> Problem:
    problem = (
        db.query(Problem)
        .filter(Problem.problem_id == problem_id, Problem.validated == True)
        .first()
    )
    if not problem:
        raise HTTPException(status_code=404, detail=f"Problem '{problem_id}' not found.")
    return problem


def _build_visible_results(
    all_cases: list[dict],
    exec_result: ExecutionResult,
) -> list[TestCaseResult]:
    """Returns test case results for visible (non-hidden) test cases only."""
    visible = [tc for tc in all_cases if not tc.get("hidden", False)]
    results = []
    for i, tc in enumerate(visible):
        got    = exec_result.test_outputs[i] if i < len(exec_result.test_outputs) else ""
        passed = exec_result.test_results[i] if i < len(exec_result.test_results) else False
        results.append(TestCaseResult(
            input=tc["input"],
            expected=tc["output"],
            got=got,
            passed=passed,
        ))
    return results


def _store_problem_from_brain_b(
    mini_problem: dict,
    concept:      str,
    db:           Session,
) -> Optional[str]:
    """
    Validates and stores a Brain B generated mini_problem into the problem bank.
    Returns problem_id if stored, None if validation fails.
    NEVER stores unvalidated problems.
    """
    is_valid, reason = validate_problem(mini_problem)
    if not is_valid:
        log.warning(
            "brain_b_problem_rejected",
            reason=reason,
            concept=concept,
        )
        return None

    problem_id = f"brainb_{uuid.uuid4().hex[:12]}"
    test_cases = mini_problem["test_cases"]
    total      = len(test_cases)
    n_hidden   = sum(1 for tc in test_cases if tc.get("hidden", False))
    ratio      = n_hidden / total if total > 0 else 0.0

    # Map difficulty to difficulty_score
    _diff_score = {"easy": 0.25, "medium": 0.55, "hard": 0.80}
    difficulty  = mini_problem.get("difficulty", "easy").lower()

    new_problem = Problem(
        problem_id=problem_id,
        title=f"Practice: {mini_problem['statement'][:50]}",
        statement=mini_problem["statement"],
        concept_tags=json.dumps(mini_problem.get("concept_tags", [concept])),
        primary_concept=concept,
        difficulty=difficulty,
        difficulty_score=_diff_score.get(difficulty, 0.25),
        prerequisite_concepts=json.dumps([]),
        test_cases=json.dumps(test_cases),
        hidden_ratio=round(ratio, 3),
        expected_complexity=None,
        created_by="brain_b",
        validated=True,
        faculty_reviewed=False,
    )
    db.add(new_problem)
    db.flush()

    log.info(
        "brain_b_problem_stored",
        problem_id=problem_id,
        concept=concept,
        difficulty=difficulty,
    )
    return problem_id


def _build_next_problem_schema(
    student_id: str,
    concept:    str,
    db:         Session,
) -> Optional[NextProblemSchema]:
    """Selects next problem for student and returns lightweight schema."""
    seen_ids = [
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
        return None

    problem = db.query(Problem).filter(Problem.problem_id == result.problem_id).first()
    if not problem:
        return None

    concept_tags: list[str] = json.loads(problem.concept_tags)
    return NextProblemSchema(
        problem_id=problem.problem_id,
        title=problem.title,
        statement=problem.statement,
        difficulty=problem.difficulty,
        concept_tags=concept_tags,
    )


# ─────────────────────────────────────────────
# POST /submit
# ─────────────────────────────────────────────

@router.post(
    "/submit",
    response_model=SubmitResponse,
    summary="Submit student code — runs full adaptive pipeline",
    responses={
        429: {"model": CooldownResponse, "description": "Rapid resubmit cooldown active"},
    },
)
def submit_code(
    body: SubmitRequest,
    db:   Session = Depends(get_db),
) -> SubmitResponse:
    """
    Full 10-step AdaptLab submission pipeline:

        1. Validate student and problem exist
        2. Load problem test cases from DB
        3. Run code in sandbox executor
        4. Run anti-gaming checks (hardcoding + rapid resubmit)
        5. Extract code features via AST
        6. Call Brain A → structured feedback
        7. Check escalation rules
        8. If escalated → call Brain B → deep explanation
        9. Update capability scores (EMA)
        10. Select next problem via question_selector
        → Persist Submission to DB
        → Return SubmitResponse
    """
    submission_id = str(uuid.uuid4())
    log.info(
        "submit_start",
        submission_id=submission_id,
        student_id=body.student_id,
        problem_id=body.problem_id,
    )

    # ── Step 1: Validate student + problem ───────────────────────────────────
    student = _get_student_or_404(body.student_id, db)
    problem = _get_problem_or_404(body.problem_id, db)
    all_cases: list[dict] = json.loads(problem.test_cases)

    # ── Step 2: Anti-gaming rapid-resubmit check (BEFORE execution) ──────────
    gaming_pre: AntiGamingResult = check_anti_gaming(
        student_id=body.student_id,
        current_code=body.code,
        db=db,
        problem_id=body.problem_id,
    )
    if gaming_pre.cooldown_active:
        log.warning(
            "submit_cooldown_active",
            student_id=body.student_id,
            seconds_remaining=gaming_pre.cooldown_seconds_remaining,
        )
        raise HTTPException(
            status_code=429,
            detail={
                "detail": "Too many submissions. Please wait before resubmitting.",
                "cooldown_seconds_remaining": gaming_pre.cooldown_seconds_remaining,
            },
        )

    # ── Step 3: Execute code in sandbox ──────────────────────────────────────
    exec_result: ExecutionResult = run_code(
        student_code=body.code,
        test_cases=all_cases,
        language="python",
    )

    # ── Step 4: Post-execution anti-gaming (hardcoding detection) ────────────
    gaming_post: AntiGamingResult = check_anti_gaming(
        student_id=body.student_id,
        current_code=body.code,
        db=db,
        visible_pass_rate=exec_result.visible_pass_rate,
        hidden_pass_rate=exec_result.hidden_pass_rate,
    )

    # If hardcoding flagged: cap pass_rate at 0.3 (spec Section 4.4)
    effective_pass_rate = exec_result.pass_rate
    if gaming_post.flagged and gaming_post.reason in ("visible_only_pass", "suspicious_gap"):
        effective_pass_rate = min(exec_result.pass_rate, 0.3)
        log.warning(
            "gaming_cap_applied",
            student_id=body.student_id,
            original_pass_rate=exec_result.pass_rate,
            capped_pass_rate=effective_pass_rate,
            reason=gaming_post.reason,
        )

    # ── Step 5: Extract code features via AST ────────────────────────────────
    features: dict = extract_features(body.code).to_dict()
    error_type: str = features.get("error_type", "none")

    # ── Step 6: Call Brain A — structured feedback ───────────────────────────
    brain_a_input = BrainAInput(
        student_code=body.code,
        problem_statement=problem.statement,
        pass_rate=effective_pass_rate,
        visible_pass_rate=exec_result.visible_pass_rate,
        hidden_pass_rate=exec_result.hidden_pass_rate,
        compiled=exec_result.compiled,
        error_type=error_type,
        code_features=features,
        test_failures=[
            {
                "input":    all_cases[i]["input"],
                "expected": all_cases[i]["output"],
                "got":      exec_result.test_outputs[i] if i < len(exec_result.test_outputs) else "",
                "passed":   exec_result.test_results[i] if i < len(exec_result.test_results) else False,
            }
            for i, tc in enumerate(all_cases)
            if not tc.get("hidden", False)
        ],
    )
    brain_a_out: BrainAOutput = get_feedback(brain_a_input)

    # ── Step 7: Check escalation rules ───────────────────────────────────────
    escalation: EscalationResult = check_escalation(
        student_id=body.student_id,
        problem_id=body.problem_id,
        submission_id=submission_id,
        concept=problem.primary_concept,
        pass_rate=effective_pass_rate,
        compiled=exec_result.compiled,
        error_type=error_type,
        deep_explain_requested=body.deep_explain,
        db=db,
    )

    # ── Step 8: Brain B — deep explanation (escalation only) ─────────────────
    brain_b_out:     Optional[BrainBOutput]  = None
    deep_explanation: Optional[DeepExplanationSchema] = None

    if escalation.should_escalate:
        # Build capability history for context
        from database.models import CapabilityScore as CS
        cap_rows = (
            db.query(CS)
            .filter(CS.student_id == body.student_id)
            .all()
        )
        capability_history = {row.concept: row.score for row in cap_rows}

        brain_b_input = BrainBInput(
            student_code=body.code,
            problem_statement=problem.statement,
            test_failures=[
                {
                    "input":    all_cases[i]["input"],
                    "expected": all_cases[i]["output"],
                    "got":      exec_result.test_outputs[i] if i < len(exec_result.test_outputs) else "",
                    "passed":   exec_result.test_results[i] if i < len(exec_result.test_results) else False,
                }
                for i in range(len(all_cases))
                if not all_cases[i].get("hidden", False)
            ],
            code_features=features,
            escalation_reason=escalation.reason or "student_request",
            capability_history=capability_history,
            concept=problem.primary_concept,
        )
        brain_b_out = get_deep_explanation(brain_b_input)

        # Validate + store Brain B mini_problem if present
        stored_mini_problem = None
        if brain_b_out.mini_problem:
            _store_problem_from_brain_b(
                mini_problem=brain_b_out.mini_problem,
                concept=problem.primary_concept,
                db=db,
            )
            stored_mini_problem = brain_b_out.mini_problem

        deep_explanation = DeepExplanationSchema(
            explanation=brain_b_out.explanation,
            step_by_step=brain_b_out.step_by_step,
            alternative_approach=brain_b_out.alternative_approach,
            mini_problem=stored_mini_problem,
        )

    # ── Step 9: Update capability scores (EMA) ───────────────────────────────
    cap_update = update_capability(
        student_id=body.student_id,
        concept=problem.primary_concept,
        pass_rate=effective_pass_rate,
        compiled=exec_result.compiled,
        timeout=exec_result.timeout,
        runtime_error=exec_result.runtime_error,
        error_type=error_type,
        db=db,
    )

    # ── Step 10: Select next problem ─────────────────────────────────────────
    # Flush current submission first so seen_ids includes this problem
    _persist_submission(
        submission_id=submission_id,
        student_id=body.student_id,
        problem_id=body.problem_id,
        code=body.code,
        exec_result=exec_result,
        effective_pass_rate=effective_pass_rate,
        error_type=error_type,
        brain_a_out=brain_a_out,
        brain_b_out=brain_b_out,
        escalation=escalation,
        gaming=gaming_post,
        db=db,
    )

    next_problem = _build_next_problem_schema(
        student_id=body.student_id,
        concept=problem.primary_concept,
        db=db,
    )

    db.commit()

    log.info(
        "submit_complete",
        submission_id=submission_id,
        student_id=body.student_id,
        problem_id=body.problem_id,
        pass_rate=effective_pass_rate,
        escalated=escalation.should_escalate,
        gaming_flagged=gaming_post.flagged,
    )

    # ── Build response ────────────────────────────────────────────────────────
    visible_results = _build_visible_results(all_cases, exec_result)

    return SubmitResponse(
        submission_id=submission_id,
        pass_rate=round(effective_pass_rate, 4),
        visible_results=visible_results,
        feedback=FeedbackSchema(
            text=brain_a_out.feedback_text,
            mistake_category=brain_a_out.mistake_category,
            difficulty_signal=brain_a_out.difficulty_signal,
        ),
        deep_explanation=deep_explanation,
        next_problem=next_problem,
        capability_update=CapabilityUpdateSchema(
            concept=cap_update.concept,
            old_score=round(cap_update.old_score, 4),
            new_score=round(cap_update.new_score, 4),
        ),
        escalated=escalation.should_escalate,
        gaming_flagged=gaming_post.flagged,
    )


# ─────────────────────────────────────────────
# DB persistence helper (called inside pipeline)
# ─────────────────────────────────────────────

def _persist_submission(
    submission_id:      str,
    student_id:         str,
    problem_id:         str,
    code:               str,
    exec_result:        ExecutionResult,
    effective_pass_rate: float,
    error_type:         str,
    brain_a_out:        BrainAOutput,
    brain_b_out:        Optional[BrainBOutput],
    escalation:         EscalationResult,
    gaming:             AntiGamingResult,
    db:                 Session,
) -> None:
    """Persists the Submission ORM row. Called before next-problem selection."""
    brain_a_json = json.dumps({
        "feedback_text":      brain_a_out.feedback_text,
        "mistake_category":   brain_a_out.mistake_category,
        "difficulty_signal":  brain_a_out.difficulty_signal,
    })

    brain_b_json = None
    if brain_b_out is not None:
        brain_b_json = json.dumps({
            "explanation":          brain_b_out.explanation,
            "step_by_step":         brain_b_out.step_by_step,
            "alternative_approach": brain_b_out.alternative_approach,
            "has_mini_problem":     brain_b_out.mini_problem is not None,
        })

    row = Submission(
        submission_id=submission_id,
        student_id=student_id,
        problem_id=problem_id,
        code=code,
        pass_rate=round(effective_pass_rate, 4),
        visible_pass_rate=round(exec_result.visible_pass_rate, 4),
        hidden_pass_rate=round(exec_result.hidden_pass_rate, 4) if exec_result.hidden_pass_rate is not None else None,
        error_type=error_type,
        compiled=exec_result.compiled,
        brain_a_feedback=brain_a_json,
        brain_b_feedback=brain_b_json,
        escalated=escalation.should_escalate,
        escalation_reason=escalation.reason,
        gaming_flagged=gaming.flagged,
        gaming_reason=gaming.reason,
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.flush()   # flush so problem_id appears in seen_ids for next-problem query
