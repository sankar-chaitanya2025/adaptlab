# AdaptLab — A Student's Journey (End-to-End)

> This document walks through the complete experience of a student using AdaptLab, from first registration to mastery.

---

## 🎓 Act 1: Getting Started

**Priya** is a 2nd-year CSE student at IISc. Her professor has set up AdaptLab for the Data Structures lab.

### Step 1 — Registration
Priya opens AdaptLab and registers with her college ID.

```
POST /student/register
{
  "student_id": "IISC2024_priya",
  "name": "Priya Sharma",
  "email": "priya@iisc.ac.in"
}
```

She's now in the system with a **default capability score of 0.5** across all concepts — the system knows nothing about her yet.

---

## 🧩 Act 2: First Problem

### Step 2 — Getting a Problem
Priya's lab starts with **loops**. She requests her first problem:

```
GET /problems/next?student_id=IISC2024_priya&concept=loops
```

AdaptLab's **Question Selector** evaluates her:
- Capability score: **0.5** (default — new student)
- Zone: **2 (Medium)** — the Learning Zone sweet spot
- It picks a medium-difficulty loops problem she hasn't seen before

She gets: **"Sum of Array"** — given a list of integers, print their sum.

### Step 3 — Writing & Submitting Code
Priya writes her solution and submits:

```
POST /submit
{
  "student_id": "IISC2024_priya",
  "problem_id": "P001",
  "code": "import json\nnums = json.loads(input())\ntotal = 0\nfor n in nums:\n    total += n\nprint(total)",
  "deep_explain": false
}
```

**Behind the scenes, 10 things happen in under 3 seconds:**

1. ✅ Her student record and problem are validated
2. 🛡️ Anti-gaming checks she's not resubmitting too fast
3. 🏃 Her code runs in a **sandboxed executor** against visible + hidden test cases
4. 🔍 Post-execution anti-gaming checks for hardcoding (comparing visible vs hidden pass rates)
5. 🧬 **AST Feature Extractor** analyzes her code structure — loops, recursion, complexity
6. 🧠 **Brain A** (Qwen 1.5B) generates concise feedback in < 3 seconds
7. 📊 Escalation rules check if she needs deeper help
8. 📈 Her **capability score** updates via EMA math
9. 🎯 **Question Selector** picks her next challenge
10. 💾 Everything is persisted to the database

### Step 4 — Getting Her Results
She gets back:

```json
{
  "pass_rate": 1.0,
  "visible_results": [
    {"input": "[1,2,3]", "expected": "6", "got": "6", "passed": true},
    {"input": "[0,0,0]", "expected": "0", "got": "0", "passed": true}
  ],
  "feedback": {
    "text": "Great job! Your solution correctly iterates through the array.",
    "mistake_category": "unknown",
    "difficulty_signal": "harder"
  },
  "capability_update": {
    "concept": "loops",
    "old_score": 0.5,
    "new_score": 0.575
  },
  "next_problem": {
    "title": "Find Maximum Element",
    "difficulty": "medium",
    "concept_tags": ["loops", "arrays"]
  }
}
```

**What Priya sees:**
- ✅ She passed all visible test cases!
- 📝 Brief feedback (no solution given — just guidance)
- 📈 Her loops score went up: **0.50 → 0.575**
- 🎯 Next challenge: "Find Maximum Element" (slightly harder, as Brain A signaled)

---

## 😰 Act 3: Struggling (Escalation)

### Step 5 — A Harder Problem
Priya attempts **"Reverse Linked List"** — a recursion problem. She submits code with a **missing base case**.

**What happens:**
- Pass rate: **0.0** — none of the test cases pass
- Feature Extractor detects: `missing_base_case = true`
- Brain A feedback: *"Your recursive function never stops. Add a condition to return when the list is empty."*
- Capability score drops: **recursion: 0.5 → 0.44**

### Step 6 — She Tries Again… and Again
She submits two more attempts. Still failing. The **Escalation Engine** detects:

- ❌ 3 consecutive failures on the same concept → **streak rule triggered**
- Her recursion score is now **0.38** → below the **low_capability threshold (0.40)**

### Step 7 — Brain B Activates 🧠🧠
The system automatically escalates to **Brain B** (Qwen 7B — the bigger, slower model):

```json
{
  "deep_explanation": {
    "explanation": "Recursion requires a base case — a condition where the function stops calling itself...",
    "step_by_step": [
      "Step 1: Identify when the linked list is empty (head == None)",
      "Step 2: Return None as the base case",
      "Step 3: Recursively reverse the rest of the list",
      "Step 4: Set the next node's pointer back to the current node"
    ],
    "alternative_approach": "You could also reverse a linked list iteratively using three pointers...",
    "mini_problem": {
      "statement": "Write a function that computes factorial(n) using recursion with a proper base case.",
      "test_cases": [...]
    }
  }
}
```

**What Priya sees:**
- 📖 A detailed, step-by-step explanation of WHERE and WHY she's stuck
- 🔄 An alternative approach she could try
- 🧩 A **simpler practice problem** (factorial) to build her base-case intuition

### Step 8 — She Clicks "I Want a Deeper Explanation"
Even without automatic escalation, Priya can **request** Brain B anytime:

```json
{ "deep_explain": true }
```

This always triggers Brain B — because sometimes students just want more help, and that's okay.

---

## 📈 Act 4: Growth & Adaptation

### The Adaptive Loop
Over the next few weeks, Priya keeps coding. The system **adapts to her**:

| Week | Concept | Score | Zone | What Happens |
|------|---------|-------|------|-------------|
| 1 | loops | 0.50 → 0.72 | 2→3 | Problems get harder |
| 1 | arrays | 0.50 → 0.61 | 2 | Stays in learning zone |
| 2 | recursion | 0.38 → 0.55 | 0→2 | Recovers with Brain B help |
| 3 | sorting | 0.50 → 0.48 | 2 | Struggles, gets easier problems |
| 4 | dictionaries | 0.50 → 0.78 | 2→3 | Natural talent, gets challenged |

**Key adaptive behaviors:**
- When she's **strong** (zone 3): harder problems, Brain A says "harder"
- When she's **struggling** (zone 0): falls back to prerequisite concepts
- When she's in the **sweet spot** (zone 2): optimal challenge level — maximum learning
- **Never repeats** the same problem twice
- **Never shows** hidden test cases (prevents gaming)

---

## 🛡️ Act 5: Anti-Gaming

### The System Catches Cheating Attempts

**Scenario A — Hardcoding:**
Priya's friend Arjun tries to hardcode answers by looking at visible test cases:
```python
if input() == "[1,2,3]":
    print("6")
```
- Visible pass rate: **100%** (matches the expected outputs)
- Hidden pass rate: **0%** (fails all hidden tests)
- 🚨 **Hardcoding detected!** Score capped at 0.3

**Scenario B — Rapid Resubmit:**
Another student submits the same code 5 times in 10 seconds:
- 🚨 **Cooldown activated!** HTTP 429 — "Try again in 30 seconds"

---

## 👩‍🏫 Act 6: Faculty View

Priya's professor, Dr. Rao, checks the **Faculty Dashboard**:

```
GET /faculty/dashboard
```

He sees:
- 📊 Class-wide concept weakness: **recursion** (mean score 0.42)
- 🚨 5 students in Zone 0 on recursion — need intervention
- 📈 Escalation rate: 18% — healthy, system is helping
- 🎮 Gaming flag rate: 3% — anti-gaming is working

He can also check individual students:
```
GET /faculty/class-overview
```
- Students ranked by performance (weakest first)
- At-a-glance: who needs help, who's mastering the material

---

## 🏆 The Result

After 4 weeks of using AdaptLab:
- Priya went from **0.5** (unknown) to **0.72** average across all concepts
- She spent most of her time in the **Learning Zone** — challenged but not overwhelmed
- Brain B helped her break through her **recursion wall**
- The system adapted **25+ problems** to her exact skill level — no two students got the same problem sequence

**AdaptLab didn't teach Priya — it coached her.**
