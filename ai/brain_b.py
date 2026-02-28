# ai/brain_b.py
# AdaptLab — Qwen2.5-Coder-7B via Ollama. Deep explanation + mini-problem generator.
# Called ONLY on escalation. Slower than Brain A — timeout is 30 seconds.
# Imports from: utils/constants.py, utils/logger.py

import json
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

from utils.constants import (
    BRAIN_B_MAX_TOKENS,
    BRAIN_B_MODEL,
    BRAIN_B_TIMEOUT_S,
    OLLAMA_BASE_URL,
    OLLAMA_GENERATE_PATH,
)
from utils.logger import get_logger

log = get_logger("ai.brain_b")


# ─────────────────────────────────────────────
# Input / Output contracts
# ─────────────────────────────────────────────

@dataclass
class BrainBInput:
    student_code:       str
    problem_statement:  str
    test_failures:      list        # [{input, expected, got, passed}] — visible failures only
    code_features:      dict        # CodeFeatures as dict
    escalation_reason:  str         # 'student_request' | 'streak' | 'low_capability' | 'conceptual_gap'
    capability_history: dict        # {concept: score} for context
    concept:            str


@dataclass
class BrainBOutput:
    explanation:          str
    step_by_step:         list[str]
    alternative_approach: str
    mini_problem:         Optional[dict]    # None if generation disabled or parse failed
    raw_response:         Optional[str] = None
    parse_error:          bool = False


# ─────────────────────────────────────────────
# System prompt — exact text from spec
# ─────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are an expert programming tutor. A student is stuck. "
    "Respond with ONLY a JSON object with these exact keys: "
    '{"explanation": "2-3 sentences explaining the conceptual misunderstanding", '
    '"step_by_step": ["Step 1: ...", "Step 2: ...", "Step 3: ..."], '
    '"alternative_approach": "one paragraph suggesting a different strategy", '
    '"mini_problem": {'
    '"statement": "a simpler problem targeting the same concept gap", '
    '"concept_tags": ["concept1"], '
    '"difficulty": "easy", '
    '"reference_solution": "working Python code", '
    '"test_cases": [{"input": "...", "output": "...", "hidden": false}]'
    "}} "
    "The mini_problem MUST have a correct reference_solution. "
    "Do not give away the solution to the original problem. "
    "Respond ONLY with the JSON object."
)


# ─────────────────────────────────────────────
# Safe defaults — returned on any failure
# ─────────────────────────────────────────────

def _safe_defaults(raw: Optional[str] = None) -> BrainBOutput:
    return BrainBOutput(
        explanation=(
            "There appears to be a conceptual misunderstanding with this problem. "
            "Review the core concept and try breaking the problem into smaller steps."
        ),
        step_by_step=[
            "Step 1: Re-read the problem statement carefully.",
            "Step 2: Identify what inputs and outputs are expected.",
            "Step 3: Think about which data structure or algorithm pattern fits best.",
        ],
        alternative_approach=(
            "Consider starting with a brute-force approach to verify correctness, "
            "then optimise once the logic is solid."
        ),
        mini_problem=None,
        raw_response=raw,
        parse_error=True,
    )


# ─────────────────────────────────────────────
# Prompt builder
# ─────────────────────────────────────────────

def _build_prompt(inp: BrainBInput) -> str:
    """
    Constructs the user-turn message for Brain B.
    Includes: student code, problem statement, test failures, features,
    escalation reason, and capability history for personalised tutoring.
    """
    # Truncate student code to avoid token overflow on 7B model
    code_snippet = inp.student_code[:2000] if len(inp.student_code) > 2000 else inp.student_code

    # Include at most 3 test failures for brevity
    failures = [f for f in inp.test_failures if not f.get("passed", True)][:3]

    payload = {
        "concept":             inp.concept,
        "escalation_reason":   inp.escalation_reason,
        "problem_statement":   inp.problem_statement[:500],
        "student_code":        code_snippet,
        "test_failures":       failures,
        "capability_history":  {
            k: round(v, 3) for k, v in inp.capability_history.items()
        },
        "code_features": {
            "error_type":           inp.code_features.get("error_type", "none"),
            "uses_recursion":       inp.code_features.get("uses_recursion", False),
            "nested_loops":         inp.code_features.get("nested_loops", False),
            "complexity_estimate":  inp.code_features.get("complexity_estimate", "unknown"),
            "missing_base_case":    inp.code_features.get("missing_base_case", False),
            "brute_force_detected": inp.code_features.get("brute_force_detected", False),
        },
    }
    return json.dumps(payload, indent=2)


# ─────────────────────────────────────────────
# Ollama call
# ─────────────────────────────────────────────

def _call_ollama(prompt: str) -> tuple[Optional[str], Optional[str]]:
    """
    POSTs to Ollama REST API using the 7B model.
    Returns (response_text, error_message).
    Timeout is BRAIN_B_TIMEOUT_S (30 seconds) — 7B is slower than 1.5B.
    """
    url = f"{OLLAMA_BASE_URL}{OLLAMA_GENERATE_PATH}"
    payload = {
        "model":  BRAIN_B_MODEL,
        "prompt": f"{_SYSTEM_PROMPT}\n\n{prompt}",
        "stream": False,
        "options": {
            "num_predict": BRAIN_B_MAX_TOKENS,
            "temperature": 0.4,
            "top_p": 0.9,
        },
    }

    try:
        resp = requests.post(url, json=payload, timeout=BRAIN_B_TIMEOUT_S)
        resp.raise_for_status()
        data = resp.json()
        raw_text: str = data.get("response", "").strip()
        return raw_text, None

    except requests.exceptions.Timeout:
        log.warning("brain_b_timeout", timeout_s=BRAIN_B_TIMEOUT_S)
        return None, "timeout"

    except requests.exceptions.ConnectionError:
        log.error("brain_b_connection_error", url=url)
        return None, "connection_error"

    except requests.exceptions.HTTPError as exc:
        log.error(
            "brain_b_http_error",
            status=exc.response.status_code if exc.response else "?",
        )
        return None, f"http_error:{exc}"

    except Exception as exc:
        log.exception("brain_b_unexpected_error", error=str(exc))
        return None, str(exc)


# ─────────────────────────────────────────────
# JSON parser + field validator
# ─────────────────────────────────────────────

_VALID_DIFFICULTIES = {"easy", "medium", "hard"}


def _parse_response(raw: str) -> Optional[BrainBOutput]:
    """
    Parses Brain B's raw JSON response.
    Strips markdown fences if present.
    Returns None on any unrecoverable parse error.
    Partially valid responses are accepted with safe fallbacks per field.
    """
    text = raw.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(
            line for line in lines
            if not line.strip().startswith("```")
        ).strip()

    # Attempt direct parse
    try:
        obj: dict[str, Any] = json.loads(text)
    except json.JSONDecodeError:
        # Try to extract first JSON object from mixed text
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start == -1 or end == 0:
            return None
        try:
            obj = json.loads(text[start:end])
        except json.JSONDecodeError:
            return None

    # ── Parse explanation ─────────────────────
    explanation = str(obj.get("explanation", "")).strip()
    if not explanation:
        explanation = (
            "There is a conceptual misunderstanding. "
            "Review the core algorithm pattern for this concept."
        )

    # ── Parse step_by_step ────────────────────
    raw_steps = obj.get("step_by_step", [])
    if isinstance(raw_steps, list) and len(raw_steps) > 0:
        step_by_step = [str(s).strip() for s in raw_steps if str(s).strip()]
    else:
        step_by_step = [
            "Step 1: Re-read the problem statement.",
            "Step 2: Trace through your code with a small example.",
            "Step 3: Identify where the output diverges from expected.",
        ]

    # ── Parse alternative_approach ────────────
    alternative_approach = str(obj.get("alternative_approach", "")).strip()
    if not alternative_approach:
        alternative_approach = (
            "Consider a different algorithmic strategy. "
            "Start simple and build up complexity once the basic case works."
        )

    # ── Parse mini_problem ────────────────────
    mini_problem = _parse_mini_problem(obj.get("mini_problem"))

    return BrainBOutput(
        explanation=explanation,
        step_by_step=step_by_step,
        alternative_approach=alternative_approach,
        mini_problem=mini_problem,
        raw_response=raw,
        parse_error=False,
    )


def _parse_mini_problem(raw_mp: Any) -> Optional[dict]:
    """
    Validates and sanitises the mini_problem dict from Brain B.
    Returns None if mini_problem is absent or structurally invalid.
    Does NOT run the reference_solution — that is validator.py's job.
    """
    if not isinstance(raw_mp, dict):
        return None

    required = ["statement", "concept_tags", "difficulty", "reference_solution", "test_cases"]
    for field_name in required:
        if not raw_mp.get(field_name):
            log.warning("mini_problem_missing_field", field=field_name)
            return None

    # Validate difficulty
    difficulty = str(raw_mp.get("difficulty", "easy")).strip().lower()
    if difficulty not in _VALID_DIFFICULTIES:
        difficulty = "easy"

    # Validate concept_tags
    concept_tags = raw_mp.get("concept_tags", [])
    if not isinstance(concept_tags, list) or len(concept_tags) == 0:
        log.warning("mini_problem_invalid_concept_tags")
        return None

    # Validate test_cases
    test_cases = raw_mp.get("test_cases", [])
    if not isinstance(test_cases, list) or len(test_cases) == 0:
        log.warning("mini_problem_no_test_cases")
        return None

    # Sanitise individual test cases
    clean_cases = []
    for tc in test_cases:
        if not isinstance(tc, dict):
            continue
        clean_cases.append({
            "input":  str(tc.get("input", "")),
            "output": str(tc.get("output", "")),
            "hidden": bool(tc.get("hidden", False)),
        })

    if len(clean_cases) == 0:
        return None

    # Ensure at least one hidden test case (HIDDEN_RATIO_MIN enforcement pre-validator)
    has_hidden = any(tc["hidden"] for tc in clean_cases)
    if not has_hidden:
        # Promote the last test case to hidden
        clean_cases[-1]["hidden"] = True

    return {
        "statement":          str(raw_mp["statement"]).strip(),
        "concept_tags":       [str(t).strip() for t in concept_tags],
        "difficulty":         difficulty,
        "reference_solution": str(raw_mp["reference_solution"]).strip(),
        "test_cases":         clean_cases,
    }


# ─────────────────────────────────────────────
# Public interface
# ─────────────────────────────────────────────

def get_deep_explanation(inp: BrainBInput) -> BrainBOutput:
    """
    Main entry point. Calls Ollama Brain B (7B model) and returns
    structured BrainBOutput with deep explanation + mini_problem.

    Failure policy (from spec):
        - If JSON parse fails → return explanation only, mini_problem=None
        - If Ollama call fails → return safe defaults
        - NEVER raise — caller always gets a valid BrainBOutput
    """
    prompt = _build_prompt(inp)

    log.info(
        "brain_b_call_start",
        concept=inp.concept,
        escalation_reason=inp.escalation_reason,
        code_length=len(inp.student_code),
        failures_count=len([f for f in inp.test_failures if not f.get("passed", True)]),
    )

    raw, error = _call_ollama(prompt)

    if error or not raw:
        log.warning("brain_b_call_failed", error=error)
        return _safe_defaults(raw=None)

    parsed = _parse_response(raw)

    if parsed is None:
        log.warning(
            "brain_b_parse_failed",
            raw_preview=raw[:300] if raw else "",
        )
        return _safe_defaults(raw=raw)

    log.info(
        "brain_b_call_success",
        has_mini_problem=parsed.mini_problem is not None,
        step_count=len(parsed.step_by_step),
        explanation_length=len(parsed.explanation),
    )

    return parsed
