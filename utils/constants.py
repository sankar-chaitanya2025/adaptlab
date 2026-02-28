# utils/constants.py
# AdaptLab — Single source of truth for all magic numbers.
# No other file defines constants. Import from here only.

# ─────────────────────────────────────────────
# EMA CAPABILITY SCORING
# ─────────────────────────────────────────────

EMA_DEFAULT_WEIGHT: float = 0.15       # fallback weight when concept not in error map
INITIAL_SCORE: float = 0.5            # new concept starts at "unknown / average"
SCORE_MIN: float = 0.0
SCORE_MAX: float = 1.0

# SubmissionScore mapping (used in capability_engine.py)
SUBMISSION_SCORE_FULL_PASS: float        = 1.0   # pass_rate == 1.0
SUBMISSION_SCORE_PARTIAL_HIGH: float     = 0.6   # compiled, pass_rate >= 0.5
SUBMISSION_SCORE_PARTIAL_LOW: float      = 0.4   # compiled, 0 < pass_rate < 0.5
SUBMISSION_SCORE_ZERO_PASS: float        = 0.3   # compiled, pass_rate == 0.0
SUBMISSION_SCORE_SYNTAX_ERROR: float     = 0.2   # failed to compile
SUBMISSION_SCORE_TIMEOUT_CRASH: float    = 0.1   # timeout or runtime crash

# Concept weights per error_type — used to amplify EMA update for relevant concepts.
# Keys = error_type strings returned by feature_extractor.py
# Values = dict of {concept: weight} overriding EMA_DEFAULT_WEIGHT
CONCEPT_WEIGHTS: dict[str, dict[str, float]] = {
    "off_by_one":            {"loops": 0.20, "arrays": 0.05},
    "missing_base_case":     {"recursion": 0.20, "functions": 0.05},
    "wrong_data_structure":  {"dictionaries": 0.20, "arrays": 0.08},
    "brute_force_detected":  {"sorting": 0.15, "loops": 0.10},
    "generalization_failure":{"loops": 0.15, "arrays": 0.10},
    "hardcoded_values":      {"loops": 0.10, "arrays": 0.10},
    "approach_mismatch":     {"sorting": 0.15},
    "syntax_error":          {},   # no concept penalty for syntax errors
    "none":                  {},   # use EMA_DEFAULT_WEIGHT for all concepts
}

# ─────────────────────────────────────────────
# ZONE THRESHOLDS (prototype routing)
# ─────────────────────────────────────────────

ZONE_TOO_DIFFICULT: float = 0.40   # score < 0.40  → zone 0 (serve prerequisite)
ZONE_EASY_MAX: float      = 0.55   # score < 0.55  → zone 1 (easy band)
ZONE_MEDIUM_MAX: float    = 0.75   # score < 0.75  → zone 2 (medium / learning sweet spot)
# score >= 0.75                    → zone 3 (hard band / approaching mastery)

# Brain A difficulty_signal → band offset
BAND_OFFSET: dict[str, int] = {
    "easier": -1,
    "same":    0,
    "harder": +1,
}

BAND_MIN: int = 0
BAND_MAX: int = 3

# ─────────────────────────────────────────────
# ESCALATION RULES
# ─────────────────────────────────────────────

ESCALATION_STREAK: int      = 3     # consecutive failures before Brain B kicks in
ESCALATION_LOW_CAP: float   = 0.40  # capability score below this triggers escalation

# ─────────────────────────────────────────────
# SANDBOX EXECUTION LIMITS
# ─────────────────────────────────────────────

SANDBOX_TIMEOUT_SEC: int  = 5    # hard timeout per subprocess run
SANDBOX_MEMORY_MB: int    = 256  # memory limit enforced via resource module (Linux)

# ─────────────────────────────────────────────
# ANTI-GAMING DETECTION
# ─────────────────────────────────────────────

ANTI_GAME_GAP: float          = 0.40  # visible_pass_rate - hidden_pass_rate > this → flag
ANTI_GAME_VISIBLE_FULL: float = 1.0   # visible_pass_rate threshold for visible_only_pass check
ANTI_GAME_HIDDEN_THRESH: float= 0.50  # hidden_pass_rate < this (with visible==1.0) → flag
ANTI_GAME_WINDOW_MIN: int     = 3     # rolling window in minutes for rapid resubmit
ANTI_GAME_SUBMIT_MAX: int     = 5     # max submissions in window before cooldown
ANTI_GAME_DISTINCT_MIN: int   = 1     # distinct_code_versions <= this triggers cooldown
ANTI_GAME_COOLDOWN_S: int     = 60    # cooldown duration in seconds
ANTI_GAME_SCORE_CAP: float    = 0.3   # SubmissionScore hard-capped when gaming flagged

# ─────────────────────────────────────────────
# HIDDEN TEST RATIO ENFORCEMENT
# ─────────────────────────────────────────────

HIDDEN_RATIO_MIN: float = 0.30  # every problem must have >= 30% hidden test cases

# ─────────────────────────────────────────────
# OLLAMA / LLM CONFIGURATION
# ─────────────────────────────────────────────

BRAIN_A_MODEL: str    = "qwen2.5-coder:1.5b-instruct"
BRAIN_B_MODEL: str    = "qwen2.5-coder:7b-instruct"
OLLAMA_BASE_URL: str  = "http://localhost:11434"
OLLAMA_GENERATE_PATH: str = "/api/generate"

BRAIN_A_MAX_TOKENS: int   = 200    # keep feedback concise
BRAIN_B_MAX_TOKENS: int   = 1500   # deep explanation needs more room
BRAIN_A_TIMEOUT_S: int    = 3      # 1.5B model must respond within 3s
BRAIN_B_TIMEOUT_S: int    = 30     # 7B model is slower, allow 30s

# ─────────────────────────────────────────────
# GAUSSIAN UTILITY (Socratic-Zero, full version)
# Reference: Wang et al., 2025 — Equation 6
# ─────────────────────────────────────────────

GAUSSIAN_MU: float    = 0.5   # target capability score (frontier of learning)
GAUSSIAN_SIGMA: float = 0.2   # tolerance band — sharper drop-off means tighter zone
USE_GAUSSIAN: bool    = False  # False = zone-based prototype; True = Gaussian selection

# ─────────────────────────────────────────────
# VALIDATOR COMPLEXITY THRESHOLDS
# ─────────────────────────────────────────────

VALIDATOR_EASY_MAX_MS: int = 2000  # Brain B easy problems must solve in < 2000ms

# ─────────────────────────────────────────────
# PROBLEM DIFFICULTY LABELS
# ─────────────────────────────────────────────

DIFFICULTY_EASY:   str = "easy"
DIFFICULTY_MEDIUM: str = "medium"
DIFFICULTY_HARD:   str = "hard"

# ─────────────────────────────────────────────
# PROBLEM CREATOR LABELS
# ─────────────────────────────────────────────

CREATED_BY_FACULTY:  str = "faculty"
CREATED_BY_BRAIN_B:  str = "brain_b"

# ─────────────────────────────────────────────
# KNOWN CONCEPTS (prerequisite graph anchors)
# ─────────────────────────────────────────────

# Concept prerequisite map — used by question_selector.py when routing to zone 0.
# For a given concept, this defines what simpler concept to fall back to.
CONCEPT_PREREQUISITES: dict[str, str] = {
    "loops":          "variables",
    "arrays":         "loops",
    "strings":        "loops",
    "functions":      "variables",
    "recursion":      "functions",
    "dictionaries":   "arrays",
    "sorting":        "arrays",
    "dynamic_prog":   "recursion",
    "graphs":         "arrays",
    "trees":          "recursion",
    "variables":      "variables",   # root concept, no further fallback
}

# ─────────────────────────────────────────────
# SERVER CONFIGURATION
# ─────────────────────────────────────────────

SERVER_HOST: str = "0.0.0.0"
SERVER_PORT: int = 8000

