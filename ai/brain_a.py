# ai/brain_a.py
# AdaptLab — Qwen2.5-Coder-1.5B via Ollama. Structured feedback generator.
# LLM used here. All other components are deterministic.
# Imports from: utils/constants.py, utils/logger.py

import json
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

from utils.constants import (
    BRAIN_A_MAX_TOKENS,
    BRAIN_A_MODEL,
    BRAIN_A_TIMEOUT_S,
    OLLAMA_BASE_URL,
    OLLAMA_GENERATE_PATH,
)
from utils.logger import get_logger

log = get_logger("ai.brain_a")


# ─────────────────────────────────────────────
# Input / Output contracts
# ─────────────────────────────────────────────

@dataclass
class BrainAInput:
    student_code:       str
    problem_statement:  str
    pass_rate:          float
    visible_pass_rate:  float
    hidden_pass_rate:   float
    compiled:           bool
    error_type:         str
    code_features:      dict                # CodeFeatures as dict
    test_failures:      list                # [{input, expected, got, passed}]


@dataclass
class BrainAOutput:
    feedback_text:      str
    mistake_category:   str     # 'off_by_one' | 'missing_base_case' | 'wrong_data_structure' |
                                # 'brute_force' | 'hardcoded' | 'approach_mismatch' |
                                # 'syntax' | 'logic' | 'unknown'
    difficulty_signal:  str     # 'easier' | 'same' | 'harder'
    raw_response:       Optional[str] = None
    parse_error:        bool = False


# ─────────────────────────────────────────────
# System prompt — exact text from spec
# ─────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are a concise coding tutor giving feedback to a college student. "
    "Given structured evaluation data about their code submission, respond with "
    "ONLY a JSON object containing these exact keys: "
    "feedback_text (one sentence what went wrong, one sentence why, one actionable hint. "
    "No solution. No code. Under 80 words.), "
    "mistake_category (off_by_one | missing_base_case | wrong_data_structure | "
    "brute_force | hardcoded | approach_mismatch | syntax | logic | unknown), "
    "difficulty_signal (easier | same | harder). "
    "Respond ONLY with the JSON object. No preamble. No explanation."
)

# ─────────────────────────────────────────────
# Safe defaults — returned on any failure
# ─────────────────────────────────────────────

_SAFE_DEFAULTS = BrainAOutput(
    feedback_text="Review your logic and check your approach against the problem requirements.",
    mistake_category="unknown",
    difficulty_signal="same",
    parse_error=True,
)


# ─────────────────────────────────────────────
# Prompt builder
# ─────────────────────────────────────────────

def _build_prompt(inp: BrainAInput) -> str:
    """
    Builds the user-turn message. Provides all structured context
    Brain A needs to generate targeted feedback.
    """
    # Truncate student code to avoid token overflow on 1.5B model
    code_snippet = inp.student_code[:1500] if len(inp.student_code) > 1500 else inp.student_code

    # Include at most 3 visible test failures for brevity
    failures = [f for f in inp.test_failures if not f.get("passed", True)][:3]

    return json.dumps({
        "problem_statement":  inp.problem_statement[:400],
        "student_code":       code_snippet,
        "pass_rate":          inp.pass_rate,
        "compiled":           inp.compiled,
        "error_type":         inp.error_type,
        "test_failures":      failures,
        "features": {
            "uses_recursion":         inp.code_features.get("uses_recursion", False),
            "nested_loops":           inp.code_features.get("nested_loops", False),
            "loop_count":             inp.code_features.get("loop_count", 0),
            "complexity_estimate":    inp.code_features.get("complexity_estimate", "unknown"),
            "hardcoded_values":       inp.code_features.get("hardcoded_values", False),
            "missing_base_case":      inp.code_features.get("missing_base_case", False),
            "off_by_one_risk":        inp.code_features.get("off_by_one_risk", False),
            "brute_force_detected":   inp.code_features.get("brute_force_detected", False),
        },
    }, indent=2)


# ─────────────────────────────────────────────
# Ollama call
# ─────────────────────────────────────────────

def _call_ollama(prompt: str) -> tuple[Optional[str], Optional[str]]:
    """
    POSTs to Ollama REST API.
    Returns (response_text, error_message).
    Total call must complete within BRAIN_A_TIMEOUT_S (3 seconds).
    """
    url = f"{OLLAMA_BASE_URL}{OLLAMA_GENERATE_PATH}"
    payload = {
        "model":  BRAIN_A_MODEL,
        "prompt": f"{_SYSTEM_PROMPT}\n\n{prompt}",
        "stream": False,
        "options": {
            "num_predict": BRAIN_A_MAX_TOKENS,
            "temperature": 0.3,    # low temp → consistent structured output
            "top_p": 0.9,
        },
    }

    try:
        resp = requests.post(url, json=payload, timeout=BRAIN_A_TIMEOUT_S)
        resp.raise_for_status()
        data = resp.json()
        raw_text: str = data.get("response", "").strip()
        return raw_text, None

    except requests.exceptions.Timeout:
        log.warning("brain_a_timeout", timeout_s=BRAIN_A_TIMEOUT_S)
        return None, "timeout"

    except requests.exceptions.ConnectionError:
        log.error("brain_a_connection_error", url=url)
        return None, "connection_error"

    except requests.exceptions.HTTPError as exc:
        log.error("brain_a_http_error", status=exc.response.status_code if exc.response else "?")
        return None, f"http_error:{exc}"

    except Exception as exc:
        log.exception("brain_a_unexpected_error", error=str(exc))
        return None, str(exc)


# ─────────────────────────────────────────────
# JSON parser
# ─────────────────────────────────────────────

_VALID_MISTAKE_CATEGORIES = {
    "off_by_one", "missing_base_case", "wrong_data_structure",
    "brute_force", "hardcoded", "approach_mismatch",
    "syntax", "logic", "unknown",
}

_VALID_DIFFICULTY_SIGNALS = {"easier", "same", "harder"}


def _parse_response(raw: str) -> Optional[BrainAOutput]:
    """
    Attempts to parse Brain A's raw response as JSON.
    Strips markdown fences if the model wraps output in ```json ... ```.
    Returns None on any parse failure.
    """
    text = raw.strip()

    # Strip optional markdown code fences
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(
            line for line in lines
            if not line.strip().startswith("```")
        ).strip()

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

    feedback_text     = str(obj.get("feedback_text", "")).strip()
    mistake_category  = str(obj.get("mistake_category", "unknown")).strip().lower()
    difficulty_signal = str(obj.get("difficulty_signal", "same")).strip().lower()

    # Validate and sanitise
    if not feedback_text:
        feedback_text = "Review your logic carefully."

    if mistake_category not in _VALID_MISTAKE_CATEGORIES:
        mistake_category = "unknown"

    if difficulty_signal not in _VALID_DIFFICULTY_SIGNALS:
        difficulty_signal = "same"

    return BrainAOutput(
        feedback_text=feedback_text,
        mistake_category=mistake_category,
        difficulty_signal=difficulty_signal,
        raw_response=raw,
        parse_error=False,
    )


# ─────────────────────────────────────────────
# Public interface
# ─────────────────────────────────────────────

def get_feedback(inp: BrainAInput) -> BrainAOutput:
    """
    Main entry point. Calls Ollama Brain A (1.5B model) and returns
    structured BrainAOutput.

    Failure policy (from spec):
        - If JSON parse fails → return safe defaults
        - If Ollama call fails → return safe defaults
        - NEVER raise — caller always gets a valid BrainAOutput
    """
    prompt = _build_prompt(inp)

    log.info(
        "brain_a_call_start",
        pass_rate=inp.pass_rate,
        compiled=inp.compiled,
        error_type=inp.error_type,
    )

    raw, error = _call_ollama(prompt)

    if error or not raw:
        log.warning("brain_a_call_failed", error=error)
        return _SAFE_DEFAULTS

    parsed = _parse_response(raw)

    if parsed is None:
        log.warning(
            "brain_a_parse_failed",
            raw_preview=raw[:200] if raw else "",
        )
        defaults = BrainAOutput(
            feedback_text=_SAFE_DEFAULTS.feedback_text,
            mistake_category=_SAFE_DEFAULTS.mistake_category,
            difficulty_signal=_SAFE_DEFAULTS.difficulty_signal,
            raw_response=raw,
            parse_error=True,
        )
        return defaults

    log.info(
        "brain_a_call_success",
        mistake_category=parsed.mistake_category,
        difficulty_signal=parsed.difficulty_signal,
        feedback_length=len(parsed.feedback_text),
    )

    return parsed
