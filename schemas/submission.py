# schemas/submission.py
# AdaptLab — Pydantic request/response models for POST /submit.
# Single source of truth for all submission API contracts.
# Imports from: pydantic only.

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ─────────────────────────────────────────────
# Shared sub-models
# ─────────────────────────────────────────────

class TestCaseResult(BaseModel):
    """Single visible test case result returned to the frontend."""
    input:    str
    expected: str
    got:      str
    passed:   bool


class FeedbackSchema(BaseModel):
    """Brain A structured feedback payload."""
    text:               str
    mistake_category:   str     # off_by_one | missing_base_case | wrong_data_structure |
                                # brute_force | hardcoded | approach_mismatch |
                                # syntax | logic | unknown
    difficulty_signal:  str     # easier | same | harder


class DeepExplanationSchema(BaseModel):
    """Brain B structured deep explanation — present only when escalated."""
    explanation:            str
    step_by_step:           list[str]
    alternative_approach:   str
    mini_problem:           Optional[dict] = None   # validated Brain B problem or None


class NextProblemSchema(BaseModel):
    """Minimal problem object returned as the next challenge."""
    problem_id:     str
    title:          str
    statement:      str
    difficulty:     str
    concept_tags:   list[str]


class CapabilityUpdateSchema(BaseModel):
    """Capability score delta for the primary concept — shown to student."""
    concept:    str
    old_score:  float
    new_score:  float


# ─────────────────────────────────────────────
# Request model
# ─────────────────────────────────────────────

class SubmitRequest(BaseModel):
    """
    POST /submit request body.
    All fields are validated before the pipeline runs.
    """
    student_id:     str = Field(..., min_length=1, max_length=64,
                                description="Student identifier")
    problem_id:     str = Field(..., min_length=1, max_length=64,
                                description="Problem identifier")
    code:           str = Field(..., min_length=1, max_length=50_000,
                                description="Student's submitted Python code")
    deep_explain:   bool = Field(default=False,
                                 description="If True, triggers Brain B escalation")

    @field_validator("student_id", "problem_id")
    @classmethod
    def no_whitespace_ids(cls, v: str) -> str:
        """IDs must not contain leading/trailing whitespace."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("ID must be non-empty after stripping whitespace.")
        return stripped

    @field_validator("code")
    @classmethod
    def code_not_blank(cls, v: str) -> str:
        """Code must contain at least some non-whitespace characters."""
        if not v.strip():
            raise ValueError("Submitted code must not be blank.")
        return v

    model_config = {"str_strip_whitespace": False}


# ─────────────────────────────────────────────
# Response model
# ─────────────────────────────────────────────

class SubmitResponse(BaseModel):
    """
    POST /submit response body.
    Exact contract from spec Section 6:

    {
        "submission_id":      "uuid",
        "pass_rate":          0.6,
        "visible_results":    [{input, expected, got, passed}],
        "feedback":           {text, mistake_category, difficulty_signal},
        "deep_explanation":   null | {explanation, step_by_step, alternative_approach, mini_problem},
        "next_problem":       null | {problem_id, title, statement, difficulty, concept_tags},
        "capability_update":  {concept, old_score, new_score},
        "escalated":          false,
        "gaming_flagged":     false
    }
    """
    submission_id:      str
    pass_rate:          float = Field(..., ge=0.0, le=1.0)
    visible_results:    list[TestCaseResult]
    feedback:           FeedbackSchema
    deep_explanation:   Optional[DeepExplanationSchema] = None
    next_problem:       Optional[NextProblemSchema] = None
    capability_update:  CapabilityUpdateSchema
    escalated:          bool = False
    gaming_flagged:     bool = False


# ─────────────────────────────────────────────
# Cooldown / rate-limit response (HTTP 429)
# ─────────────────────────────────────────────

class CooldownResponse(BaseModel):
    """
    Returned with HTTP 429 when rapid resubmit cooldown is active.
    """
    detail:                     str = "Too many submissions. Please wait before resubmitting."
    cooldown_seconds_remaining: int


# ─────────────────────────────────────────────
# History endpoint models (used by routes_student.py)
# ─────────────────────────────────────────────

class SubmissionHistoryItem(BaseModel):
    """Single row in a student's submission history."""
    submission_id:  str
    problem_id:     str
    problem_title:  Optional[str] = None
    pass_rate:      float
    compiled:       bool
    error_type:     Optional[str] = None
    escalated:      bool
    gaming_flagged: bool
    submitted_at:   str     # ISO 8601 datetime string


class SubmissionHistoryResponse(BaseModel):
    """
    GET /student/{student_id}/history response.
    """
    student_id:     str
    total:          int
    submissions:    list[SubmissionHistoryItem]
