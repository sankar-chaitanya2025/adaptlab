# AdaptLab — Backend Architecture (End-to-End)

> How every request flows through the system, which modules talk to each other, and what math/AI drives the decisions.

---

## 🏗️ System Overview

```
┌─────────────┐     ┌──────────────────────────────────────────────┐
│   Student    │────▶│              FastAPI Server                  │
│   (Postman/  │◀────│              (main.py)                      │
│    Browser)  │     │                                              │
└─────────────┘     │  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
                    │  │ Submit   │  │ Problems │  │ Student  │   │
                    │  │ Router   │  │ Router   │  │ Router   │   │
                    │  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
                    │       │             │             │          │
                    │  ┌────▼─────────────▼─────────────▼──────┐  │
                    │  │           Core Pipeline                │  │
                    │  │  Sandbox │ Analysis │ AI │ DB          │  │
                    │  └───────────────────────────────────────┘   │
                    │                                              │
                    │  ┌──────────────┐    ┌──────────────────┐   │
                    │  │  SQLite DB   │    │  Ollama (Local)  │   │
                    │  │  adaptlab.db │    │  Qwen 1.5B / 7B │   │
                    │  └──────────────┘    └──────────────────┘   │
                    └──────────────────────────────────────────────┘
```

---

## 📁 Module Map

| Layer | Module | Role | Uses LLM? |
|-------|--------|------|-----------|
| **Entry** | `main.py` | FastAPI app, lifespan, router registration | ❌ |
| **API** | `api/routes_submit.py` | 10-step submission pipeline orchestrator | ❌ (calls AI modules) |
| **API** | `api/routes_problems.py` | Next problem & problem detail endpoints | ❌ |
| **API** | `api/routes_student.py` | Student profile, history, registration | ❌ |
| **API** | `api/routes_faculty.py` | Faculty dashboard, class overview, escalations | ❌ |
| **Sandbox** | `sandbox/executor.py` | Secure code execution with resource limits | ❌ |
| **Sandbox** | `sandbox/anti_gaming.py` | Hardcoding detection + rapid resubmit | ❌ |
| **Analysis** | `analysis/feature_extractor.py` | AST-based static code analysis | ❌ |
| **Analysis** | `analysis/capability_engine.py` | EMA capability score updates | ❌ |
| **Analysis** | `analysis/question_selector.py` | Zone-based / Gaussian problem selection | ❌ |
| **AI** | `ai/brain_a.py` | Quick feedback via Qwen 1.5B | ✅ |
| **AI** | `ai/brain_b.py` | Deep explanation via Qwen 7B | ✅ |
| **AI** | `ai/escalation.py` | Rule engine: when to call Brain B | ❌ |
| **AI** | `ai/validator.py` | Validates Brain B generated problems | ❌ |
| **DB** | `database/models.py` | 5 ORM tables (Student, Problem, Submission, CapabilityScore, EscalationLog) | ❌ |
| **DB** | `database/db.py` | SQLite connection, session factory, init | ❌ |
| **DB** | `database/seed.py` | 20 starter problems | ❌ |
| **Config** | `utils/constants.py` | All magic numbers in one place | ❌ |
| **Config** | `utils/logger.py` | Structured JSON logging | ❌ |
| **Schemas** | `schemas/*.py` | Pydantic request/response contracts | ❌ |

> **Key insight:** Only 2 out of 20 modules use an LLM. Everything else is deterministic.

---

## 🔄 The 10-Step Submit Pipeline

When `POST /submit` is called, here's exactly what happens:

### Step 1 — Validate Student + Problem
```
routes_submit.py → database/models.py
```
- Looks up `Student` by `student_id` → 404 if not found
- Looks up `Problem` by `problem_id` → 404 if not found or not validated
- Loads all test cases (visible + hidden) from the problem's JSON

### Step 2 — Anti-Gaming: Rapid Resubmit Check
```
routes_submit.py → sandbox/anti_gaming.py → check_rapid_resubmit()
```
- Queries last 5 submissions for this student+problem
- If same code submitted within 30 seconds → **HTTP 429 cooldown**
- Prevents brute-force trial-and-error

### Step 3 — Execute Code in Sandbox
```
routes_submit.py → sandbox/executor.py → run_code()
```
- Writes student code to a temp `.py` file
- Syntax-checks via `py_compile`
- Runs against each test case in a **subprocess** with:
  - Timeout: 5 seconds per test case
  - Memory limit: 128MB (Linux only, skipped on Windows)
- Collects: `pass_rate`, `visible_pass_rate`, `hidden_pass_rate`, `stderr`
- **Hidden test results are NEVER exposed to the student**

### Step 4 — Anti-Gaming: Hardcoding Detection
```
routes_submit.py → sandbox/anti_gaming.py → check_hardcoding()
```
- Compares `visible_pass_rate` vs `hidden_pass_rate`
- If visible is 100% but hidden is 0% → **hardcoding detected**
- If gap > 40% → **suspicious gap**
- Penalty: effective pass_rate capped at **0.3**

### Step 5 — Extract Code Features (AST)
```
routes_submit.py → analysis/feature_extractor.py → extract_features()
```
- Parses code into an AST (Abstract Syntax Tree)
- Detects:
  - `uses_recursion`, `nested_loops`, `loop_count`
  - `complexity_estimate`: O(1) / O(n) / O(n²) / O(n log n)
  - Error classification: `off_by_one`, `missing_base_case`, `wrong_data_structure`, `brute_force_detected`, `hardcoded_values`, `approach_mismatch`
- Returns a single `error_type` label (priority-ordered)
- **100% deterministic — no LLM**

### Step 6 — Brain A: Structured Feedback
```
routes_submit.py → ai/brain_a.py → get_feedback()
```
- Model: **Qwen2.5-Coder-1.5B** via Ollama
- Timeout: **3 seconds** (fast model, quick feedback)
- Input: problem statement, student code (truncated to 1500 chars), pass_rate, error_type, code features, visible test failures
- Output (strict JSON):
  - `feedback_text`: 1-2 sentences, no solution, no code, under 80 words
  - `mistake_category`: off_by_one | missing_base_case | brute_force | syntax | logic | ...
  - `difficulty_signal`: easier | same | harder
- **Failure policy**: If Ollama is down or JSON parse fails → return safe defaults. **Never crashes.**

### Step 7 — Escalation Check
```
routes_submit.py → ai/escalation.py → check_escalation()
```
4 rules checked in priority order:

| # | Rule | Trigger | Example |
|---|------|---------|---------|
| 1 | `student_request` | `deep_explain: true` | Student clicks "explain more" |
| 2 | `streak` | 3+ consecutive failures on same concept | Stuck on recursion |
| 3 | `low_capability` | Capability score < 0.40 | Struggling badly |
| 4 | `conceptual_gap` | Compiled but < 50% pass rate, non-surface error | Understands syntax but not logic |

If any rule fires → logged to `EscalationLog` table + Brain B is called.

### Step 8 — Brain B: Deep Explanation (Escalation Only)
```
routes_submit.py → ai/brain_b.py → get_deep_explanation()
```
- Model: **Qwen2.5-Coder-7B** via Ollama
- Timeout: **30 seconds** (larger model, more thorough)
- Only called when escalation triggers (saves compute)
- Output:
  - `explanation`: Detailed concept explanation
  - `step_by_step`: Guided solution steps (no direct code)
  - `alternative_approach`: A different way to think about it
  - `mini_problem`: A simpler practice problem (validated before storage)
- If mini_problem passes validation → stored in the **problem bank** for future students

### Step 9 — Update Capability Scores (EMA)
```
routes_submit.py → analysis/capability_engine.py → update_capability()
```

**Math — Exponential Moving Average:**
```
new_score = (1 - weight) × old_score + weight × submission_score
```

- `submission_score` mapping:
  | Condition | Score |
  |-----------|-------|
  | Full pass (100%) | 1.0 |
  | Partial pass ≥ 50% | 0.6 |
  | Partial pass < 50% | 0.4 |
  | Zero pass | 0.3 |
  | Syntax error | 0.2 |
  | Timeout/crash | 0.1 |

- `weight` depends on the **error_type × concept** combination:
  - `off_by_one` on `loops` → weight = 0.20 (high impact)
  - `missing_base_case` on `recursion` → weight = 0.20
  - Default weight = 0.15

- Score always clamped to **[0.0, 1.0]**

### Step 10 — Select Next Problem
```
routes_submit.py → analysis/question_selector.py → get_next_problem()
```

**Zone-Based Selection (default mode):**
```
Zone 0: score < 0.40  → Too Difficult → serve prerequisite concept
Zone 1: score < 0.55  → Easy band
Zone 2: score < 0.75  → Medium band (Learning Zone — optimal)
Zone 3: score ≥ 0.75  → Hard band
```

- Brain A's `difficulty_signal` applies a **±1 band offset**:
  - "easier" → band - 1
  - "same" → band stays
  - "harder" → band + 1
- If no problem in target band → falls back to band - 1
- **NEVER serves the same problem twice** to the same student

**Gaussian Selection (advanced mode, off by default):**
```
U(q | πₛ) = exp(-(sₛ - μ)² / (2σ²))
```
- Scores every available problem by how close its difficulty matches the student's frontier
- μ = 0.5 (optimal challenge point), σ = 0.2 (tolerance band)

### Final — Persist & Respond
- The `Submission` row is saved with all data (code, pass_rate, feedback, escalation, gaming flags)
- Everything committed in a single DB transaction
- Full `SubmitResponse` returned to the client

---

## 🗄️ Database Schema

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│   students   │     │   problems   │     │   submissions    │
├──────────────┤     ├──────────────┤     ├──────────────────┤
│ student_id   │◄────│              │◄────│ submission_id    │
│ name         │     │ problem_id   │     │ student_id (FK)  │
│ email        │     │ title        │     │ problem_id (FK)  │
│ created_at   │     │ statement    │     │ code             │
└──────┬───────┘     │ concept_tags │     │ pass_rate        │
       │             │ difficulty   │     │ error_type       │
       │             │ test_cases   │     │ brain_a_feedback │
       │             │ hidden_ratio │     │ brain_b_feedback │
       │             │ validated    │     │ escalated        │
       │             │ created_by   │     │ gaming_flagged   │
       │             └──────────────┘     └──────────────────┘
       │
       │         ┌──────────────────┐     ┌──────────────────┐
       ├────────▶│ capability_scores│     │ escalation_logs  │
       │         ├──────────────────┤     ├──────────────────┤
       │         │ student_id (FK)  │     │ log_id           │
       │         │ concept          │     │ student_id (FK)  │
       │         │ score            │     │ problem_id (FK)  │
       │         │ updated_at       │     │ submission_id(FK)│
       │         └──────────────────┘     │ reason           │
       │                                  │ resolved         │
       └─────────────────────────────────▶│ logged_at        │
                                          └──────────────────┘
```

---

## 🔐 Safety & Invariants

These rules are **enforced in code** and never violated:

1. **Hidden test cases are NEVER exposed** — not in responses, not in errors
2. **Brain A's `difficulty_signal` NEVER writes to capability scores** — it only biases question routing
3. **Same problem is NEVER served twice** to the same student
4. **Brain B mini-problems are ALWAYS validated** before entering the problem bank
5. **All LLM calls have safe defaults** — system NEVER crashes if Ollama is down
6. **Capability scores are always in [0.0, 1.0]** — clamped after every update
7. **Anti-gaming is checked BEFORE and AFTER execution** — two separate checks
8. **Escalation logs are immutable** — once written, can only be marked resolved

---

## 🚀 How to Run

```bash
cd adaptlab
pip install -r requirements.txt
python main.py
# Server starts on http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

For full LLM support, start Ollama with:
```bash
ollama pull qwen2.5-coder:1.5b
ollama pull qwen2.5-coder:7b
ollama serve
```
