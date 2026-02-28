# AdaptLab — Adaptive Coding Lab Platform

> A research-backed adaptive coding lab platform for college students, inspired by the **Socratic-Zero** co-evolution framework (Wang et al., 2025).

AdaptLab replaces binary pass/fail grading with LLM-based process evaluation. It builds a capability profile for each student, adapts question difficulty in real time, and escalates to deep AI explanation only when a student is genuinely stuck.

---

## How It Works

A student submits code. The system doesn't just check if the output is correct — it analyzes *how* the student thinks. It identifies where their reasoning broke down, updates their capability score for each concept, and serves them the next problem at exactly the right difficulty level. Over time, the student genuinely improves.

The system is built on three research foundations:

- **Socratic-Zero** (Wang et al., 2025) — Teacher-Solver-Generator co-evolution. Brain B maps to the Teacher, the student maps to the Solver, Brain A maps to the Generator.
- **Vygotsky's Zone of Proximal Development** — questions are served where the student succeeds ~50% of the time, not too easy, not too hard.
- **Gaussian Utility Function** — `U(q) = exp(-(s_q - 0.5)² / (2 × 0.2²))` assigns highest utility to problems at the frontier of student capability.

---

## Architecture

```
[ Student Browser ]
        ↓
[ FastAPI Backend ]
        ↓
1. Sandbox Executor        — runs code against test cases (no LLM)
2. Feature Extractor       — AST analysis, error classification (no LLM)
3. Capability Engine       — EMA score update, zone classification (no LLM)
4. Brain A (1.5B model)    — generates concise feedback (always runs)
5. Escalation Check        — deterministic rule engine (no LLM)
6. Brain B (7B model)      — deep explanation + problem generation (escalation only)
7. Question Selector       — zone-based adaptive routing (no LLM)
        ↓
[ Response → Student Dashboard + Faculty Dashboard ]
```

**Core principle:** LLMs handle only what requires language intelligence. Everything deterministic — code execution, feature extraction, capability scoring, question routing — uses pure math and logic.

---

## Dual-Brain Design

| | Brain A | Brain B |
|---|---|---|
| Model | Qwen2.5-Coder-1.5B-Instruct | Qwen2.5-Coder-7B-Instruct |
| Quantization | Q4_K_M via Ollama | Q4_K_M via Ollama |
| RAM | ~1 GB | ~4.5 GB |
| Runs | Every submission | Escalation only |
| Job | Short structured feedback | Deep explanation + mini-problem |
| Response time | < 1.5 seconds | 4–8 seconds |

---

## The Math

### Capability Score — Exponential Moving Average

```
NewScore = (1 - w) × OldScore + w × SubmissionScore
```

Where `w` is concept-weighted by error type:

| Error Type | Primary Concept Weight | Secondary |
|---|---|---|
| `off_by_one` | loops: 0.20 | arrays: 0.05 |
| `missing_base_case` | recursion: 0.20 | functions: 0.05 |
| `wrong_data_structure` | dictionaries: 0.20 | arrays: 0.08 |
| `brute_force_detected` | sorting: 0.15 | loops: 0.10 |
| Default | all concepts: 0.15 | — |

SubmissionScore mapping:

| Result | Score |
|---|---|
| All test cases passed | 1.0 |
| ≥50% passed, compiled | 0.6 |
| <50% passed, compiled | 0.4 |
| Compiled, 0% passed | 0.3 |
| Syntax error | 0.2 |
| Timeout / crash | 0.1 |

### Learning Zone Classification

| Zone | Score Range | System Response |
|---|---|---|
| Too Difficult | < 0.40 | Serve prerequisite concept |
| Learning Zone | 0.40 – 0.75 | Stay here, vary difficulty |
| Mastered | > 0.75 | Introduce harder variants |

### Gaussian Utility (Full Version)

```
U(q | π_s) = exp( -(s_q - μ)² / (2σ²) )
  μ = 0.5   target success rate
  σ = 0.2   tolerance band
```

Toggle via `USE_GAUSSIAN=True` in `.env`.

### Escalation Rules

Checked in order, returns on first match:

1. Student explicitly requested deep explanation
2. Same concept failed 3 consecutive times
3. Capability score < 0.40
4. Code compiled but logical error detected (conceptual gap)

### Anti-Gaming Detection

**Hardcoding:** `visible_pass_rate == 1.0 and hidden_pass_rate < 0.50` → cap SubmissionScore at 0.3

**Rapid resubmit:** ≥5 submissions in 3 minutes with ≤1 distinct code version → 60-second cooldown

**Hidden test ratio:** every problem must have `hidden_ratio ≥ 0.30`, enforced at insert time.

---

## File Structure

```
adaptlab/
├── main.py                          # FastAPI entry point
├── requirements.txt
├── .env
│
├── database/
│   ├── db.py                        # SQLite connection + session factory
│   ├── models.py                    # SQLAlchemy ORM — 5 tables
│   └── seed.py                      # 20 starter problems seeded on first run
│
├── sandbox/
│   ├── executor.py                  # Subprocess code runner with timeout + limits
│   └── anti_gaming.py               # Hardcoding + rapid resubmit detection
│
├── analysis/
│   ├── feature_extractor.py         # Python AST analysis → CodeFeatures
│   ├── capability_engine.py         # EMA update with feature-weighted concept map
│   └── question_selector.py         # Zone-based + Gaussian question routing
│
├── ai/
│   ├── brain_a.py                   # Qwen2.5-Coder-1.5B via Ollama
│   ├── brain_b.py                   # Qwen2.5-Coder-7B via Ollama
│   ├── escalation.py                # Deterministic escalation rule engine
│   └── validator.py                 # Brain B problem validation pipeline
│
├── api/
│   ├── routes_submit.py             # POST /submit — main pipeline (15 steps)
│   ├── routes_student.py            # GET /student/{id}/profile + history
│   ├── routes_faculty.py            # GET /faculty/dashboard
│   └── routes_problems.py           # GET /problems/next + /problems/{id}
│
├── schemas/
│   ├── submission.py                # Pydantic models for /submit
│   ├── capability.py                # Pydantic models for capability profiles
│   └── problem.py                   # Pydantic models for problem schema
│
└── utils/
    ├── constants.py                 # Single source of truth for all thresholds
    └── logger.py                    # Structured JSON logging
```

---

## Database Schema

Five tables:

- **Student** — student_id, name, email
- **Problem** — full problem metadata including concept_tags, difficulty_score, hidden test cases, prerequisite concepts
- **Submission** — code, pass rates (visible + hidden), error type, Brain A/B feedback, escalation flag, gaming flag
- **CapabilityScore** — composite PK (student_id + concept), score 0.0–1.0
- **EscalationLog** — reason, resolved flag, timestamp

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/submit` | Main submission pipeline |
| GET | `/problems/next` | Get next adaptive problem for student |
| GET | `/problems/{id}` | Get specific problem |
| GET | `/student/{id}/profile` | Student capability profile |
| GET | `/student/{id}/history` | Submission history |
| GET | `/faculty/dashboard` | Class-wide analytics |

### POST /submit — Response Shape

```json
{
  "submission_id": "uuid",
  "pass_rate": 0.6,
  "visible_results": [...],
  "feedback": {
    "text": "Your loop boundary is off by one...",
    "mistake_category": "off_by_one",
    "difficulty_signal": "same"
  },
  "deep_explanation": null,
  "next_problem": { "problem_id": "P044", "title": "...", "difficulty": "medium" },
  "capability_update": { "concept": "arrays", "old_score": 0.65, "new_score": 0.62 },
  "escalated": false,
  "gaming_flagged": false
}
```

---

## Setup & Installation

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) installed on the server
- 16GB RAM (no GPU required)

### 1. Pull AI Models

```bash
ollama pull qwen2.5-coder:1.5b
ollama pull qwen2.5-coder:7b
```

### 2. Clone & Install

```bash
git clone https://github.com/yourusername/adaptlab.git
cd adaptlab
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env if needed — defaults work out of the box
```

### 4. Run

```bash
python main.py
```

API live at `http://localhost:8000`
Interactive docs at `http://localhost:8000/docs`

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./adaptlab.db` | Database path |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `BRAIN_A_MODEL` | `qwen2.5-coder:1.5b` | Fast feedback model |
| `BRAIN_B_MODEL` | `qwen2.5-coder:7b` | Deep reasoning model |
| `SANDBOX_TIMEOUT_S` | `5` | Code execution timeout |
| `ESCALATION_STREAK` | `3` | Failures before escalation |
| `ESCALATION_LOW_CAP` | `0.40` | Score threshold for escalation |
| `HIDDEN_RATIO_MIN` | `0.30` | Minimum hidden test case ratio |
| `USE_GAUSSIAN` | `False` | Enable Gaussian question selection |
| `GAUSSIAN_MU` | `0.5` | Target success rate |
| `GAUSSIAN_SIGMA` | `0.2` | Difficulty tolerance |

---

## Hardware Requirements

Minimum for running the full system:

| Component | Requirement |
|---|---|
| RAM | 16 GB |
| CPU | Quad-core |
| Storage | 50 GB SSD |
| GPU | Not required |
| OS | Linux / Windows / macOS |

Peak RAM usage breakdown:

| Component | RAM |
|---|---|
| Brain A (1.5B Q4) | ~1 GB |
| Brain B (7B Q4) | ~4.5 GB |
| Backend + DB | ~0.5 GB |
| **Total peak** | **~6 GB of 16 GB** |

---

## Research Foundation

This project is the practical implementation of:

- **Socratic-Zero: Bootstrapping Reasoning via Data-Free Agent Co-Evolution** (Wang et al., 2025) — the Teacher-Solver-Generator co-evolution model and Gaussian utility function
- **Vygotsky's Zone of Proximal Development** — the learning zone theory behind adaptive difficulty
- **Knowledge Tracing** — modeling what a student knows over time using exponential moving averages

---

## Thesis Claims

This system is designed to prove three measurable claims in a pilot study:

1. LLM-based process evaluation produces a more accurate model of student capability than binary output-based grading
2. Adaptive question sequencing improves student capability scores over static question sets
3. The Socratic-Zero co-evolution model can be adapted from mathematical reasoning to programming problem-solving on consumer-grade hardware

---

## Contributing

This is a thesis project. Issues and suggestions welcome.

---

## License

MIT
