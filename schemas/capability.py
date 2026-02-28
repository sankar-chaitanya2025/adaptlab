# schemas/capability.py
# AdaptLab — Pydantic models for capability profiles.
# Used by: api/routes_student.py, api/routes_faculty.py
# Imports from: pydantic only.

from typing import Optional

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
# Single concept score
# ─────────────────────────────────────────────

class ConceptScoreSchema(BaseModel):
    """
    One entry in a student's capability profile.
    Maps a single concept to its current EMA score.
    """
    concept:    str
    score:      float = Field(..., ge=0.0, le=1.0,
                              description="EMA capability score clamped to [0.0, 1.0]")
    updated_at: Optional[str] = None    # ISO 8601 datetime string


# ─────────────────────────────────────────────
# Zone classification (mirrors question_selector logic)
# ─────────────────────────────────────────────

class ZoneSchema(BaseModel):
    """
    Computed learning zone for a concept.
    Mirrors zone thresholds in analysis/question_selector.py.
    """
    concept:    str
    score:      float
    zone:       int     # 0=Too Difficult | 1=Easy | 2=Medium (Learning Zone) | 3=Hard
    zone_label: str     # 'too_difficult' | 'easy' | 'learning_zone' | 'mastery'


# ─────────────────────────────────────────────
# Full student capability profile
# ─────────────────────────────────────────────

class CapabilityProfileResponse(BaseModel):
    """
    GET /student/{student_id}/profile response body.

    Returns the complete capability snapshot for a student:
    - All concept scores with zone labels
    - Weakest and strongest concepts for at-a-glance diagnostics
    - Overall profile stats (mean score, total concepts seen)
    """
    student_id:         str
    student_name:       Optional[str] = None
    total_submissions:  int = 0
    total_escalations:  int = 0
    scores:             list[ConceptScoreSchema]
    zones:              list[ZoneSchema]
    weakest_concept:    Optional[str] = None
    strongest_concept:  Optional[str] = None
    mean_score:         Optional[float] = Field(default=None, ge=0.0, le=1.0)
    concepts_seen:      int = 0


# ─────────────────────────────────────────────
# Faculty — per-student summary (used in class overview)
# ─────────────────────────────────────────────

class StudentSummarySchema(BaseModel):
    """
    One student row in the faculty class overview.
    Lightweight snapshot — no full score breakdown.
    """
    student_id:         str
    student_name:       Optional[str] = None
    mean_score:         float = Field(default=0.5, ge=0.0, le=1.0)
    weakest_concept:    Optional[str] = None
    strongest_concept:  Optional[str] = None
    total_submissions:  int = 0
    total_escalations:  int = 0
    gaming_flag_count:  int = 0
    in_learning_zone:   bool = False    # True if mean_score in [0.40, 0.75]


# ─────────────────────────────────────────────
# Faculty — concept-level class aggregates
# ─────────────────────────────────────────────

class ConceptClassStatsSchema(BaseModel):
    """
    Aggregate stats for one concept across the whole class.
    Used by faculty dashboard to identify class-wide weak spots.
    """
    concept:        str
    mean_score:     float = Field(..., ge=0.0, le=1.0)
    min_score:      float = Field(..., ge=0.0, le=1.0)
    max_score:      float = Field(..., ge=0.0, le=1.0)
    students_seen:  int     # students who have attempted this concept
    in_zone_0:      int     # count in Too Difficult zone
    in_zone_1:      int     # count in Easy zone
    in_zone_2:      int     # count in Learning Zone
    in_zone_3:      int     # count in Mastery zone


# ─────────────────────────────────────────────
# Faculty — dashboard response
# ─────────────────────────────────────────────

class FacultyDashboardResponse(BaseModel):
    """
    GET /faculty/dashboard response body.

    Provides:
    - Class-wide concept weak spots sorted by mean_score ascending
    - Escalation rate for the platform
    - Gaming flag rate
    - Total submissions and active student count
    """
    total_students:         int
    active_students:        int     # students with at least 1 submission
    total_submissions:      int
    escalation_rate:        float = Field(..., ge=0.0, le=1.0)
    gaming_flag_rate:       float = Field(..., ge=0.0, le=1.0)
    concept_stats:          list[ConceptClassStatsSchema]   # sorted by mean_score ASC
    students_in_zone_0:     int     # Too Difficult — need intervention
    students_in_learning_zone: int  # Healthy — zones 1 and 2


# ─────────────────────────────────────────────
# Faculty — class overview response
# ─────────────────────────────────────────────

class ClassOverviewResponse(BaseModel):
    """
    GET /faculty/class-overview response body.

    Returns a ranked list of all students with their summary stats.
    """
    total_students: int
    students:       list[StudentSummarySchema]   # sorted by mean_score ASC (weakest first)
