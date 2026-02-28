# ai/validator.py
# AdaptLab — Validates Brain B generated problems before inserting into problem bank.
# Returns (is_valid: bool, reason: str). No LLM involved.
# Imports from: sandbox/executor.py, utils/constants.py, utils/logger.py

from dataclasses import dataclass
from typing import Optional

from sandbox.executor import ExecutionResult, run_code
from utils.constants import HIDDEN_RATIO_MIN
from utils.logger import get_logger

log = get_logger("ai.validator")


# ─────────────────────────────────────────────
# Validation reasons — single source of truth
# ─────────────────────────────────────────────

REASON_OK                       = "ok"
REASON_MISSING_FIELDS           = "missing_fields"
REASON_INSUFFICIENT_HIDDEN      = "insufficient_hidden"
REASON_REFERENCE_FAILS          = "reference_solution_fails"
REASON_REFERENCE_TIMEOUT        = "reference_solution_timeout"
REASON_REFERENCE_SYNTAX_ERROR   = "reference_solution_syntax_error"
REASON_REFERENCE_RUNTIME_ERROR  = "reference_solution_runtime_error"
REASON_TOO_SLOW_FOR_DIFFICULTY  = "too_slow_for_difficulty"
REASON_INVALID_TEST_CASES       = "invalid_test_cases"
REASON_EMPTY_STATEMENT          = "empty_statement"

# ─────────────────────────────────────────────
# Complexity time limits per difficulty
# ─────────────────────────────────────────────

_MAX_MS_BY_DIFFICULTY = {
    "easy":   2000,
    "medium": 4000,
    "hard":   8000,
}

_REQUIRED_FIELDS = [
    "statement",
    "concept_tags",
    "difficulty",
    "reference_solution",
    "test_cases",
]

_VALID_DIFFICULTIES = {"easy", "medium", "hard"}


# ─────────────────────────────────────────────
# Step helpers
# ─────────────────────────────────────────────

def _step1_structural(mini_problem: dict) -> tuple[bool, str]:
    """
    STEP 1 — Structural check.
    Validates required fields, non-empty values, hidden ratio, test case integrity.
    Returns (ok, reason).
    """

    # ── Required fields present and non-empty ─────────
    for field_name in _REQUIRED_FIELDS:
        val = mini_problem.get(field_name)
        if val is None or val == "" or val == [] or val == {}:
            log.warning(
                "validator_structural_fail",
                reason=REASON_MISSING_FIELDS,
                missing_field=field_name,
            )
            return False, REASON_MISSING_FIELDS

    # ── Statement is a non-empty string ──────────────
    statement = mini_problem.get("statement", "")
    if not isinstance(statement, str) or len(statement.strip()) < 10:
        return False, REASON_EMPTY_STATEMENT

    # ── concept_tags is a non-empty list ─────────────
    concept_tags = mini_problem.get("concept_tags", [])
    if not isinstance(concept_tags, list) or len(concept_tags) == 0:
        return False, REASON_MISSING_FIELDS

    # ── difficulty is valid ───────────────────────────
    difficulty = str(mini_problem.get("difficulty", "")).strip().lower()
    if difficulty not in _VALID_DIFFICULTIES:
        return False, REASON_MISSING_FIELDS

    # ── reference_solution is non-empty string ────────
    ref_sol = mini_problem.get("reference_solution", "")
    if not isinstance(ref_sol, str) or len(ref_sol.strip()) == 0:
        return False, REASON_MISSING_FIELDS

    # ── test_cases: minimum 1, valid structure ────────
    test_cases = mini_problem.get("test_cases", [])
    if not isinstance(test_cases, list) or len(test_cases) == 0:
        return False, REASON_INVALID_TEST_CASES

    for tc in test_cases:
        if not isinstance(tc, dict):
            return False, REASON_INVALID_TEST_CASES
        if "input" not in tc or "output" not in tc:
            return False, REASON_INVALID_TEST_CASES

    # ── Hidden ratio enforcement ──────────────────────
    # HIDDEN_RATIO_MIN = 0.30 (from spec Section 4.4)
    total     = len(test_cases)
    n_hidden  = sum(1 for tc in test_cases if tc.get("hidden", False))
    ratio     = n_hidden / total if total > 0 else 0.0

    if ratio < HIDDEN_RATIO_MIN:
        log.warning(
            "validator_structural_fail",
            reason=REASON_INSUFFICIENT_HIDDEN,
            hidden_ratio=round(ratio, 3),
            required=HIDDEN_RATIO_MIN,
            total_cases=total,
            hidden_cases=n_hidden,
        )
        return False, REASON_INSUFFICIENT_HIDDEN

    return True, REASON_OK


def _step2_execution(mini_problem: dict) -> tuple[bool, str, Optional[ExecutionResult]]:
    """
    STEP 2 — Execution check.
    Runs reference_solution through sandbox executor against all test cases.
    Returns (ok, reason, execution_result).
    """
    reference_solution = mini_problem["reference_solution"]
    test_cases         = mini_problem["test_cases"]

    result: ExecutionResult = run_code(
        student_code=reference_solution,
        test_cases=test_cases,
        language="python",
    )

    # Syntax error in reference solution
    if not result.compiled:
        log.warning(
            "validator_execution_fail",
            reason=REASON_REFERENCE_SYNTAX_ERROR,
            stderr=result.stderr[:200],
        )
        return False, REASON_REFERENCE_SYNTAX_ERROR, result

    # Timeout
    if result.timeout:
        log.warning(
            "validator_execution_fail",
            reason=REASON_REFERENCE_TIMEOUT,
            elapsed_ms=result.execution_time_ms,
        )
        return False, REASON_REFERENCE_TIMEOUT, result

    # Runtime error (non-zero exit but compiled)
    if result.runtime_error and result.pass_rate < 1.0:
        log.warning(
            "validator_execution_fail",
            reason=REASON_REFERENCE_RUNTIME_ERROR,
            stderr=result.stderr[:200],
        )
        return False, REASON_REFERENCE_RUNTIME_ERROR, result

    # Reference solution doesn't pass all test cases
    if result.pass_rate < 1.0:
        log.warning(
            "validator_execution_fail",
            reason=REASON_REFERENCE_FAILS,
            pass_rate=result.pass_rate,
            visible=f"{result.passed_visible}/{result.total_visible}",
            hidden=f"{result.passed_hidden}/{result.total_hidden}",
        )
        return False, REASON_REFERENCE_FAILS, result

    return True, REASON_OK, result


def _step3_complexity(
    mini_problem: dict,
    execution_result: ExecutionResult,
) -> tuple[bool, str]:
    """
    STEP 3 — Complexity sanity check.
    Rejects problems whose reference solution is too slow for the declared difficulty.
    """
    difficulty    = str(mini_problem.get("difficulty", "easy")).strip().lower()
    elapsed_ms    = execution_result.execution_time_ms
    max_ms        = _MAX_MS_BY_DIFFICULTY.get(difficulty, _MAX_MS_BY_DIFFICULTY["hard"])

    if elapsed_ms > max_ms:
        log.warning(
            "validator_complexity_fail",
            reason=REASON_TOO_SLOW_FOR_DIFFICULTY,
            difficulty=difficulty,
            elapsed_ms=elapsed_ms,
            max_ms=max_ms,
        )
        return False, REASON_TOO_SLOW_FOR_DIFFICULTY

    return True, REASON_OK


# ─────────────────────────────────────────────
# Public interface
# ─────────────────────────────────────────────

def validate_problem(mini_problem: dict) -> tuple[bool, str]:
    """
    Validates a Brain B generated mini_problem before inserting into the problem bank.

    Three-step pipeline (spec Section 7.7):
        Step 1 — Structural: required fields, types, hidden_ratio >= 0.30
        Step 2 — Execution:  reference_solution passes all test cases (pass_rate == 1.0)
        Step 3 — Complexity: execution time within limits for declared difficulty

    Returns:
        (True,  'ok')                           — all checks pass, safe to store
        (False, 'missing_fields')               — required field absent or empty
        (False, 'insufficient_hidden')          — hidden_ratio < 0.30
        (False, 'invalid_test_cases')           — test_cases malformed
        (False, 'empty_statement')              — statement too short
        (False, 'reference_solution_fails')     — pass_rate < 1.0
        (False, 'reference_solution_timeout')   — executor timed out
        (False, 'reference_solution_syntax_error') — syntax error in reference
        (False, 'reference_solution_runtime_error') — runtime crash
        (False, 'too_slow_for_difficulty')      — too slow for declared difficulty

    FALLBACK RULE (spec Section 7.7):
        If validation fails, the caller (routes_submit.py) must serve a fallback
        problem from the existing bank. NEVER store an unvalidated Brain B problem.
        This function itself does NOT insert into DB — that is routes_submit.py's job.
    """
    if not isinstance(mini_problem, dict):
        log.warning("validator_invalid_input", type=type(mini_problem).__name__)
        return False, REASON_MISSING_FIELDS

    problem_id_hint = mini_problem.get("statement", "")[:40]

    log.info(
        "validator_start",
        statement_hint=problem_id_hint,
        difficulty=mini_problem.get("difficulty"),
        concept_tags=mini_problem.get("concept_tags"),
    )

    # ── Step 1: Structural check ──────────────
    ok, reason = _step1_structural(mini_problem)
    if not ok:
        return False, reason

    # ── Step 2: Execution check ───────────────
    ok, reason, exec_result = _step2_execution(mini_problem)
    if not ok:
        return False, reason

    # ── Step 3: Complexity sanity ─────────────
    ok, reason = _step3_complexity(mini_problem, exec_result)
    if not ok:
        return False, reason

    log.info(
        "validator_passed",
        statement_hint=problem_id_hint,
        difficulty=mini_problem.get("difficulty"),
        execution_time_ms=exec_result.execution_time_ms,
    )

    return True, REASON_OK
