# schemas/problem.py
# AdaptLab — Pydantic models for problem schema.
# Used by: api/routes_problems.py, api/routes_submit.py, ai/validator.py
# Imports from: pydantic only.

from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ─────────────────────────────────────────────
# Shared sub-models
# ─────────────────────────────────────────────

class TestCaseSchema(BaseModel):
    """
    Single test case as stored in the DB and served to the frontend.
    Hidden test cases are included in execution but NEVER returned to the student.
    """
    input:  str
    output: str
    hidden: bool = False


class VisibleTestCaseSchema(BaseModel):
    """
    Visible-only test case — safe to send to student.
    Hidden field stripped entirely to prevent inference.
    """
    input:  str
    output: str


# ─────────────────────────────────────────────
# Problem response — full internal representation
# (used server-side only, never serialised directly to students)
# ─────────────────────────────────────────────

class ProblemFullSchema(BaseModel):
    """
    Full internal problem representation including all test cases.
    Used by the executor and validator — NEVER sent to student.
    """
    problem_id:             str
    title:                  str
    statement:              str
    concept_tags:           list[str]
    primary_concept:        str
    difficulty:             str
    difficulty_score:       float = Field(..., ge=0.0, le=1.0)
    prerequisite_concepts:  list[str] = []
    test_cases:             list[TestCaseSchema]
    hidden_ratio:           float = Field(..., ge=0.0, le=1.0)
    expected_complexity:    Optional[str] = None
    created_by:             str = "faculty"
    validated:              bool = True
    faculty_reviewed:       bool = False


# ─────────────────────────────────────────────
# Problem response — student-facing
# Hidden test cases stripped; only visible test cases shown as examples
# ─────────────────────────────────────────────

class ProblemStudentSchema(BaseModel):
    """
    Student-facing problem representation.
    Hidden test cases are stripped.
    Only visible test cases are included as examples.

    Returned by:
        GET /problems/{problem_id}
        GET /problems/next
    """
    problem_id:             str
    title:                  str
    statement:              str
    concept_tags:           list[str]
    primary_concept:        str
    difficulty:             str
    expected_complexity:    Optional[str] = None
    example_cases:          list[VisibleTestCaseSchema] = []    # visible only
    total_test_cases:       int     # total count including hidden — lets student know how many
    hidden_test_count:      int     # count of hidden tests (number, not content)


# ─────────────────────────────────────────────
# Next problem response
# ─────────────────────────────────────────────

class NextProblemResponse(BaseModel):
    """
    GET /problems/next response body.

    Returns the problem selected by question_selector for this student,
    along with routing metadata for debugging / faculty inspection.
    """
    problem:            ProblemStudentSchema
    selection_mode:     str     # 'zone_based' | 'gaussian'
    band:               int     # -1 if gaussian mode
    zone:               int     # -1 if gaussian mode
    band_offset:        int
    fallback_used:      bool


# ─────────────────────────────────────────────
# Problem detail response (GET /problems/{id})
# ─────────────────────────────────────────────

class ProblemDetailResponse(BaseModel):
    """
    GET /problems/{problem_id} response body.
    Returns student-safe view of the problem.
    """
    problem: ProblemStudentSchema


# ─────────────────────────────────────────────
# Faculty — problem create request
# (for future faculty problem creation endpoint)
# ─────────────────────────────────────────────

class ProblemCreateRequest(BaseModel):
    """
    Request body for faculty creating a new problem manually.
    Validates all required fields at input boundary.
    """
    title:                  str = Field(..., min_length=3, max_length=200)
    statement:              str = Field(..., min_length=20, max_length=5000)
    concept_tags:           list[str] = Field(..., min_length=1)
    primary_concept:        str = Field(..., min_length=1)
    difficulty:             str = Field(..., pattern=r"^(easy|medium|hard)$")
    difficulty_score:       float = Field(..., ge=0.0, le=1.0)
    prerequisite_concepts:  list[str] = []
    test_cases:             list[TestCaseSchema] = Field(..., min_length=2)
    expected_complexity:    Optional[str] = None

    @field_validator("concept_tags")
    @classmethod
    def concept_tags_not_empty_strings(cls, v: list[str]) -> list[str]:
        """Each tag must be a non-empty string."""
        cleaned = [t.strip() for t in v if t.strip()]
        if not cleaned:
            raise ValueError("concept_tags must contain at least one non-empty tag.")
        return cleaned

    @field_validator("test_cases")
    @classmethod
    def enforce_hidden_ratio(cls, v: list[TestCaseSchema]) -> list[TestCaseSchema]:
        """
        Enforces hidden_ratio >= 0.30 at input boundary (spec Section 4.4).
        Rejects faculty-created problems where fewer than 30% of test cases are hidden.
        """
        if len(v) == 0:
            raise ValueError("At least 2 test cases required.")
        n_hidden = sum(1 for tc in v if tc.hidden)
        ratio    = n_hidden / len(v)
        if ratio < 0.30:
            raise ValueError(
                f"hidden_ratio is {ratio:.2f}. At least 30% of test cases must be hidden "
                f"(spec Section 4.4). Got {n_hidden} hidden out of {len(v)} total."
            )
        return v


# ─────────────────────────────────────────────
# Faculty — problem create response
# ─────────────────────────────────────────────

class ProblemCreateResponse(BaseModel):
    """
    Response body after a faculty member creates a new problem.
    """
    problem_id:     str
    title:          str
    message:        str = "Problem created and added to the problem bank."
    validated:      bool
    faculty_reviewed: bool


# ─────────────────────────────────────────────
# Faculty — problem list response
# ─────────────────────────────────────────────

class ProblemListItem(BaseModel):
    """
    One row in the faculty problem bank listing.
    """
    problem_id:         str
    title:              str
    primary_concept:    str
    difficulty:         str
    difficulty_score:   float
    created_by:         str     # 'faculty' | 'brain_b'
    validated:          bool
    faculty_reviewed:   bool
    total_test_cases:   int
    hidden_ratio:       float


class ProblemListResponse(BaseModel):
    """
    GET /faculty/problems response body.
    """
    total:    int
    problems: list[ProblemListItem]
