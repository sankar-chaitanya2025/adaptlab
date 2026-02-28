# database/models.py
# AdaptLab — SQLAlchemy ORM models for all 5 tables.
# Imports from: sqlalchemy only. Zero internal dependencies.

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# ─────────────────────────────────────────────
# TABLE 1: Student
# ─────────────────────────────────────────────

class Student(Base):
    __tablename__ = "students"

    student_id  = Column(String, primary_key=True, default=_uuid)
    name        = Column(String, nullable=False)
    email       = Column(String, nullable=False, unique=True)
    created_at  = Column(DateTime, nullable=False, default=_now)

    # Relationships
    submissions       = relationship("Submission",     back_populates="student", cascade="all, delete-orphan")
    capability_scores = relationship("CapabilityScore", back_populates="student", cascade="all, delete-orphan")
    escalation_logs   = relationship("EscalationLog",  back_populates="student", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Student id={self.student_id} name={self.name}>"


# ─────────────────────────────────────────────
# TABLE 2: Problem
# ─────────────────────────────────────────────

class Problem(Base):
    __tablename__ = "problems"

    problem_id              = Column(String, primary_key=True)
    title                   = Column(String, nullable=False)
    statement               = Column(Text, nullable=False)

    # Stored as JSON strings — e.g. '["arrays","loops"]'
    concept_tags            = Column(Text, nullable=False)
    primary_concept         = Column(String, nullable=False)

    difficulty              = Column(String, nullable=False)          # 'easy' | 'medium' | 'hard'
    difficulty_score        = Column(Float, nullable=False)           # 0.0 – 1.0
    prerequisite_concepts   = Column(Text, nullable=True)             # JSON list
    test_cases              = Column(Text, nullable=False)            # JSON list of {input, output, hidden}
    hidden_ratio            = Column(Float, nullable=False)           # enforced >= 0.30 at insert
    expected_complexity     = Column(String, nullable=True)           # 'O(n)', 'O(n^2)', etc.

    created_by              = Column(String, nullable=False, default="faculty")   # 'faculty' | 'brain_b'
    validated               = Column(Boolean, nullable=False, default=True)
    faculty_reviewed        = Column(Boolean, nullable=False, default=False)

    # Relationships
    submissions     = relationship("Submission",   back_populates="problem")
    escalation_logs = relationship("EscalationLog", back_populates="problem")

    def __repr__(self) -> str:
        return f"<Problem id={self.problem_id} title={self.title} difficulty={self.difficulty}>"


# ─────────────────────────────────────────────
# TABLE 3: Submission
# ─────────────────────────────────────────────

class Submission(Base):
    __tablename__ = "submissions"

    submission_id       = Column(String, primary_key=True, default=_uuid)
    student_id          = Column(String, ForeignKey("students.student_id"), nullable=False)
    problem_id          = Column(String, ForeignKey("problems.problem_id"), nullable=False)

    code                = Column(Text, nullable=False)

    # Execution results
    pass_rate           = Column(Float, nullable=False)        # all test cases combined (incl. hidden)
    visible_pass_rate   = Column(Float, nullable=False)        # visible test cases only
    hidden_pass_rate    = Column(Float, nullable=True)         # hidden test cases only; None if no hidden

    compiled            = Column(Boolean, nullable=True)
    error_type          = Column(String, nullable=True)        # from feature_extractor.py

    # AI feedback
    brain_a_feedback    = Column(Text, nullable=True)          # JSON string from Brain A
    brain_b_feedback    = Column(Text, nullable=True)          # JSON string from Brain B; NULL if not escalated

    # Escalation
    escalated           = Column(Boolean, nullable=False, default=False)
    escalation_reason   = Column(String, nullable=True)

    # Anti-gaming
    gaming_flagged      = Column(Boolean, nullable=False, default=False)
    gaming_reason       = Column(String, nullable=True)

    submitted_at        = Column(DateTime, nullable=False, default=_now)

    # Relationships
    student         = relationship("Student", back_populates="submissions")
    problem         = relationship("Problem", back_populates="submissions")
    escalation_logs = relationship("EscalationLog", back_populates="submission", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Submission id={self.submission_id} student={self.student_id} problem={self.problem_id} pass_rate={self.pass_rate}>"


# ─────────────────────────────────────────────
# TABLE 4: CapabilityScore
# Composite PK: (student_id, concept)
# ─────────────────────────────────────────────

class CapabilityScore(Base):
    __tablename__ = "capability_scores"
    __table_args__ = (
        UniqueConstraint("student_id", "concept", name="uq_student_concept"),
    )

    student_id  = Column(String, ForeignKey("students.student_id"), primary_key=True, nullable=False)
    concept     = Column(String, primary_key=True, nullable=False)
    score       = Column(Float, nullable=False, default=0.5)     # clamped to [0.0, 1.0]
    updated_at  = Column(DateTime, nullable=False, default=_now)

    # Relationship
    student = relationship("Student", back_populates="capability_scores")

    def __repr__(self) -> str:
        return f"<CapabilityScore student={self.student_id} concept={self.concept} score={self.score:.3f}>"


# ─────────────────────────────────────────────
# TABLE 5: EscalationLog
# ─────────────────────────────────────────────

class EscalationLog(Base):
    __tablename__ = "escalation_logs"

    log_id          = Column(String, primary_key=True, default=_uuid)
    student_id      = Column(String, ForeignKey("students.student_id"), nullable=False)
    problem_id      = Column(String, ForeignKey("problems.problem_id"), nullable=False)
    submission_id   = Column(String, ForeignKey("submissions.submission_id"), nullable=False)
    reason          = Column(String, nullable=False)               # 'student_request' | 'streak' | 'low_capability' | 'conceptual_gap'
    resolved        = Column(Boolean, nullable=False, default=False)
    logged_at       = Column(DateTime, nullable=False, default=_now)

    # Relationships
    student    = relationship("Student",    back_populates="escalation_logs")
    problem    = relationship("Problem",    back_populates="escalation_logs")
    submission = relationship("Submission", back_populates="escalation_logs")

    def __repr__(self) -> str:
        return f"<EscalationLog id={self.log_id} student={self.student_id} reason={self.reason}>"


# ─────────────────────────────────────────────
# DB-level enforcement: hidden_ratio >= 0.30
# Fires on INSERT and UPDATE of Problem rows.
# ─────────────────────────────────────────────

@event.listens_for(Problem, "before_insert")
@event.listens_for(Problem, "before_update")
def enforce_hidden_ratio(mapper, connection, target: Problem) -> None:
    from utils.constants import HIDDEN_RATIO_MIN
    if target.hidden_ratio is not None and target.hidden_ratio < HIDDEN_RATIO_MIN:
        raise ValueError(
            f"Problem '{target.problem_id}' has hidden_ratio={target.hidden_ratio:.2f}, "
            f"minimum required is {HIDDEN_RATIO_MIN}. Rejecting insert/update."
        )
