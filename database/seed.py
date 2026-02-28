# database/seed.py
# AdaptLab — Seeds 20 starter problems into the DB on first run.
# Imports from: database/db.py, database/models.py

import json

from sqlalchemy.orm import Session

from database.models import Problem
from utils.logger import get_logger

log = get_logger("database.seed")


def seed_problems(db: Session) -> None:
    """Insert all 20 starter problems. Called only when problems table is empty."""
    problems = _build_problems()
    for p in problems:
        db.add(Problem(**p))
    db.flush()
    log.info("seed_complete", total=len(problems))


def _tc(input_val: str, output_val: str, hidden: bool) -> dict:
    """Helper to build a single test case dict."""
    return {"input": input_val, "output": output_val, "hidden": hidden}


def _build_problems() -> list[dict]:
    return [

        # ─────────────────────────────────────────────
        # P001 — Sum of a List | loops | easy
        # ─────────────────────────────────────────────
        {
            "problem_id": "P001",
            "title": "Sum of a List",
            "statement": (
                "Given a list of integers on one line, print their sum.\n"
                "Read input with: import json; nums = json.loads(input())\n"
                "Example: [1,2,3] -> 6"
            ),
            "concept_tags": json.dumps(["loops", "arrays"]),
            "primary_concept": "loops",
            "difficulty": "easy",
            "difficulty_score": 0.2,
            "prerequisite_concepts": json.dumps(["variables"]),
            "expected_complexity": "O(n)",
            "hidden_ratio": 0.5,
            "created_by": "faculty",
            "validated": True,
            "faculty_reviewed": True,
            "test_cases": json.dumps([
                _tc("[1,2,3]",    "6",  False),
                _tc("[0,0,0]",    "0",  False),
                _tc("[-1,-2,-3]", "-6", True),
                _tc("[]",         "0",  True),
            ]),
        },

        # ─────────────────────────────────────────────
        # P002 — Find Maximum Element | arrays | easy
        # ─────────────────────────────────────────────
        {
            "problem_id": "P002",
            "title": "Find Maximum Element",
            "statement": (
                "Given a list of integers, print the largest element.\n"
                "Read input with: import json; nums = json.loads(input())\n"
                "Example: [3,1,4] -> 4"
            ),
            "concept_tags": json.dumps(["loops", "arrays"]),
            "primary_concept": "arrays",
            "difficulty": "easy",
            "difficulty_score": 0.25,
            "prerequisite_concepts": json.dumps(["variables", "loops"]),
            "expected_complexity": "O(n)",
            "hidden_ratio": 0.5,
            "created_by": "faculty",
            "validated": True,
            "faculty_reviewed": True,
            "test_cases": json.dumps([
                _tc("[3,1,4,1,5]",   "5",   False),
                _tc("[1]",           "1",   False),
                _tc("[-3,-1,-4]",    "-1",  True),
                _tc("[100,99,101]",  "101", True),
            ]),
        },

        # ─────────────────────────────────────────────
        # P003 — Reverse a String | strings | easy
        # ─────────────────────────────────────────────
        {
            "problem_id": "P003",
            "title": "Reverse a String",
            "statement": (
                "Given a string, print it reversed.\n"
                "Read input with: s = input()\n"
                "Example: hello -> olleh"
            ),
            "concept_tags": json.dumps(["strings", "loops"]),
            "primary_concept": "strings",
            "difficulty": "easy",
            "difficulty_score": 0.25,
            "prerequisite_concepts": json.dumps(["variables", "loops"]),
            "expected_complexity": "O(n)",
            "hidden_ratio": 0.5,
            "created_by": "faculty",
            "validated": True,
            "faculty_reviewed": True,
            "test_cases": json.dumps([
                _tc("hello",   "olleh",   False),
                _tc("a",       "a",       False),
                _tc("racecar", "racecar", True),
                _tc("",        "",        True),
            ]),
        },

        # ─────────────────────────────────────────────
        # P004 — Count Occurrences | arrays | easy
        # ─────────────────────────────────────────────
        {
            "problem_id": "P004",
            "title": "Count Occurrences",
            "statement": (
                "Count how many times a number appears in a list.\n"
                "First line: the list (JSON). Second line: the target integer.\n"
                "Read with: import json; nums = json.loads(input()); target = int(input())\n"
                "Example: [1,2,2,3,2] / 2 -> 3"
            ),
            "concept_tags": json.dumps(["arrays", "loops"]),
            "primary_concept": "arrays",
            "difficulty": "easy",
            "difficulty_score": 0.3,
            "prerequisite_concepts": json.dumps(["variables", "loops"]),
            "expected_complexity": "O(n)",
            "hidden_ratio": 0.5,
            "created_by": "faculty",
            "validated": True,
            "faculty_reviewed": True,
            "test_cases": json.dumps([
                _tc("[1,2,2,3,2]\n2", "3", False),
                _tc("[5,5,5]\n5",     "3", False),
                _tc("[1,2,3]\n4",     "0", True),
                _tc("[]\n1",          "0", True),
            ]),
        },

        # ─────────────────────────────────────────────
        # P005 — Fibonacci (Recursive) | recursion | medium
        # ─────────────────────────────────────────────
        {
            "problem_id": "P005",
            "title": "Fibonacci Sequence",
            "statement": (
                "Return the Nth Fibonacci number using recursion. fib(0)=0, fib(1)=1.\n"
                "Read input with: n = int(input())\n"
                "Example: 5 -> 5"
            ),
            "concept_tags": json.dumps(["recursion", "functions"]),
            "primary_concept": "recursion",
            "difficulty": "medium",
            "difficulty_score": 0.55,
            "prerequisite_concepts": json.dumps(["functions", "loops"]),
            "expected_complexity": "O(2^n)",
            "hidden_ratio": 0.5,
            "created_by": "faculty",
            "validated": True,
            "faculty_reviewed": True,
            "test_cases": json.dumps([
                _tc("0",  "0",  False),
                _tc("5",  "5",  False),
                _tc("1",  "1",  True),
                _tc("10", "55", True),
            ]),
        },

        # ─────────────────────────────────────────────
        # P006 — Two Sum | dictionaries | medium
        # ─────────────────────────────────────────────
        {
            "problem_id": "P006",
            "title": "Two Sum",
            "statement": (
                "Given a list and a target, print the two indices (space-separated, ascending) "
                "of numbers that sum to the target. Assume exactly one solution.\n"
                "First line: JSON list. Second line: target integer.\n"
                "Read with: import json; nums = json.loads(input()); target = int(input())\n"
                "Example: [2,7,11,15] / 9 -> 0 1"
            ),
            "concept_tags": json.dumps(["arrays", "dictionaries"]),
            "primary_concept": "dictionaries",
            "difficulty": "medium",
            "difficulty_score": 0.6,
            "prerequisite_concepts": json.dumps(["arrays", "loops"]),
            "expected_complexity": "O(n)",
            "hidden_ratio": 0.5,
            "created_by": "faculty",
            "validated": True,
            "faculty_reviewed": True,
            "test_cases": json.dumps([
                _tc("[2,7,11,15]\n9", "0 1", False),
                _tc("[3,2,4]\n6",     "1 2", False),
                _tc("[3,3]\n6",       "0 1", True),
                _tc("[1,5,3,7]\n8",   "1 3", True),
            ]),
        },

        # ─────────────────────────────────────────────
        # P007 — Binary Search | sorting | medium
        # ─────────────────────────────────────────────
        {
            "problem_id": "P007",
            "title": "Binary Search",
            "statement": (
                "Implement binary search on a sorted list. Print index of target, -1 if not found.\n"
                "First line: sorted JSON list. Second line: target integer.\n"
                "Read with: import json; nums = json.loads(input()); target = int(input())\n"
                "Example: [1,3,5,7,9] / 5 -> 2"
            ),
            "concept_tags": json.dumps(["arrays", "loops", "sorting"]),
            "primary_concept": "sorting",
            "difficulty": "medium",
            "difficulty_score": 0.65,
            "prerequisite_concepts": json.dumps(["arrays", "loops"]),
            "expected_complexity": "O(log n)",
            "hidden_ratio": 0.5,
            "created_by": "faculty",
            "validated": True,
            "faculty_reviewed": True,
            "test_cases": json.dumps([
                _tc("[1,3,5,7,9]\n5", "2",  False),
                _tc("[1,3,5,7,9]\n1", "0",  False),
                _tc("[1,3,5,7,9]\n6", "-1", True),
                _tc("[2,4,6,8]\n8",   "3",  True),
            ]),
        },

        # ─────────────────────────────────────────────
        # P008 — Valid Parentheses | strings | medium
        # ─────────────────────────────────────────────
        {
            "problem_id": "P008",
            "title": "Valid Parentheses",
            "statement": (
                "Check if a bracket string containing '(', ')', '{', '}', '[', ']' is valid.\n"
                "Print True or False.\n"
                "Read with: s = input()\n"
                "Example: ()[]{} -> True"
            ),
            "concept_tags": json.dumps(["strings", "arrays"]),
            "primary_concept": "strings",
            "difficulty": "medium",
            "difficulty_score": 0.65,
            "prerequisite_concepts": json.dumps(["arrays", "loops"]),
            "expected_complexity": "O(n)",
            "hidden_ratio": 0.5,
            "created_by": "faculty",
            "validated": True,
            "faculty_reviewed": True,
            "test_cases": json.dumps([
                _tc("()[]{}", "True",  False),
                _tc("(]",     "False", False),
                _tc("{[]}",   "True",  True),
                _tc("([)]",   "False", True),
            ]),
        },

        # ─────────────────────────────────────────────
        # P009 — Word Frequency | dictionaries | medium
        # ─────────────────────────────────────────────
        {
            "problem_id": "P009",
            "title": "Word Frequency",
            "statement": (
                "Given a sentence, print a dict of word frequencies sorted by key.\n"
                "Read with: s = input()\n"
                "Print with: print(dict(sorted(freq.items())))\n"
                "Example: 'hello world hello' -> {'hello': 2, 'world': 1}"
            ),
            "concept_tags": json.dumps(["dictionaries", "strings", "loops"]),
            "primary_concept": "dictionaries",
            "difficulty": "medium",
            "difficulty_score": 0.55,
            "prerequisite_concepts": json.dumps(["strings", "loops"]),
            "expected_complexity": "O(n)",
            "hidden_ratio": 0.5,
            "created_by": "faculty",
            "validated": True,
            "faculty_reviewed": True,
            "test_cases": json.dumps([
                _tc("hello world hello",
                    "{'hello': 2, 'world': 1}", False),
                _tc("a b c a b a",
                    "{'a': 3, 'b': 2, 'c': 1}", False),
                _tc("one",
                    "{'one': 1}", True),
                _tc("the cat sat on the mat",
                    "{'cat': 1, 'mat': 1, 'on': 1, 'sat': 1, 'the': 2}", True),
            ]),
        },

        # ─────────────────────────────────────────────
        # P010 — Merge Sorted Lists | sorting | hard
        # ─────────────────────────────────────────────
        {
            "problem_id": "P010",
            "title": "Merge Sorted Lists",
            "statement": (
                "Merge two sorted lists into one sorted list. Print the result.\n"
                "First line: first sorted JSON list. Second line: second sorted JSON list.\n"
                "Read with: import json; a = json.loads(input()); b = json.loads(input())\n"
                "Example: [1,3,5] / [2,4,6] -> [1, 2, 3, 4, 5, 6]"
            ),
            "concept_tags": json.dumps(["arrays", "loops", "sorting"]),
            "primary_concept": "sorting",
            "difficulty": "hard",
            "difficulty_score": 0.8,
            "prerequisite_concepts": json.dumps(["arrays", "loops", "sorting"]),
            "expected_complexity": "O(n+m)",
            "hidden_ratio": 0.5,
            "created_by": "faculty",
            "validated": True,
            "faculty_reviewed": True,
            "test_cases": json.dumps([
                _tc("[1,3,5]\n[2,4,6]",    "[1, 2, 3, 4, 5, 6]", False),
                _tc("[1,2]\n[3,4]",        "[1, 2, 3, 4]",       False),
                _tc("[]\n[1,2,3]",         "[1, 2, 3]",          True),
                _tc("[-3,-1,0]\n[-2,2,4]", "[-3, -2, -1, 0, 2, 4]", True),
            ]),
        },

        # ─────────────────────────────────────────────
        # P011 — Factorial (Recursive) | recursion | medium
        # ─────────────────────────────────────────────
        {
            "problem_id": "P011",
            "title": "Factorial via Recursion",
            "statement": (
                "Compute the factorial of N using recursion. factorial(0) = 1.\n"
                "Read with: n = int(input())\n"
                "Example: 5 -> 120"
            ),
            "concept_tags": json.dumps(["recursion", "functions"]),
            "primary_concept": "recursion",
            "difficulty": "medium",
            "difficulty_score": 0.5,
            "prerequisite_concepts": json.dumps(["functions", "loops"]),
            "expected_complexity": "O(n)",
            "hidden_ratio": 0.5,
            "created_by": "faculty",
            "validated": True,
            "faculty_reviewed": True,
            "test_cases": json.dumps([
                _tc("5",  "120",     False),
                _tc("0",  "1",       False),
                _tc("1",  "1",       True),
                _tc("10", "3628800", True),
            ]),
        },

        # ─────────────────────────────────────────────
        # P012 — Tower of Hanoi Move Count | recursion | hard
        # ─────────────────────────────────────────────
        {
            "problem_id": "P012",
            "title": "Tower of Hanoi Move Count",
            "statement": (
                "Return the minimum number of moves to solve Tower of Hanoi with N disks.\n"
                "Formula: 2^N - 1. Implement recursively.\n"
                "Read with: n = int(input())\n"
                "Example: 3 -> 7"
            ),
            "concept_tags": json.dumps(["recursion", "functions"]),
            "primary_concept": "recursion",
            "difficulty": "hard",
            "difficulty_score": 0.78,
            "prerequisite_concepts": json.dumps(["recursion", "functions"]),
            "expected_complexity": "O(2^n)",
            "hidden_ratio": 0.5,
            "created_by": "faculty",
            "validated": True,
            "faculty_reviewed": True,
            "test_cases": json.dumps([
                _tc("1",  "1",    False),
                _tc("3",  "7",    False),
                _tc("5",  "31",   True),
                _tc("10", "1023", True),
            ]),
        },

        # ─────────────────────────────────────────────
        # P013 — Climbing Stairs (DP) | dynamic_prog | hard
        # ─────────────────────────────────────────────
        {
            "problem_id": "P013",
            "title": "Climbing Stairs",
            "statement": (
                "You can climb 1 or 2 steps at a time. "
                "How many distinct ways can you reach step N?\n"
                "Read with: n = int(input())\n"
                "Example: 3 -> 3  (1+1+1, 1+2, 2+1)"
            ),
            "concept_tags": json.dumps(["dynamic_prog", "recursion"]),
            "primary_concept": "dynamic_prog",
            "difficulty": "hard",
            "difficulty_score": 0.75,
            "prerequisite_concepts": json.dumps(["recursion", "arrays"]),
            "expected_complexity": "O(n)",
            "hidden_ratio": 0.5,
            "created_by": "faculty",
            "validated": True,
            "faculty_reviewed": True,
            "test_cases": json.dumps([
                _tc("1",  "1",  False),
                _tc("3",  "3",  False),
                _tc("5",  "8",  True),
                _tc("10", "89", True),
            ]),
        },

        # ─────────────────────────────────────────────
        # P014 — Minimum Coin Change (DP) | dynamic_prog | hard
        # ─────────────────────────────────────────────
        {
            "problem_id": "P014",
            "title": "Minimum Coin Change",
            "statement": (
                "Given a list of coin denominations and an amount, "
                "print the minimum number of coins needed. Print -1 if impossible.\n"
                "First line: JSON list of coin values. Second line: target amount.\n"
                "Read with: import json; coins = json.loads(input()); amount = int(input())\n"
                "Example: [1,5,10,25] / 36 -> 3"
            ),
            "concept_tags": json.dumps(["dynamic_prog", "arrays"]),
            "primary_concept": "dynamic_prog",
            "difficulty": "hard",
            "difficulty_score": 0.85,
            "prerequisite_concepts": json.dumps(["recursion", "arrays", "loops"]),
            "expected_complexity": "O(n*amount)",
            "hidden_ratio": 0.5,
            "created_by": "faculty",
            "validated": True,
            "faculty_reviewed": True,
            "test_cases": json.dumps([
                _tc("[1,5,10,25]\n36", "3",  False),
                _tc("[1,2,5]\n11",     "3",  False),
                _tc("[2]\n3",          "-1", True),
                _tc("[1,5,10]\n0",     "0",  True),
            ]),
        },

        # ─────────────────────────────────────────────
        # P015 — Number of Islands (Graph BFS/DFS) | graphs | hard
        # ─────────────────────────────────────────────
        {
            "problem_id": "P015",
            "title": "Number of Islands",
            "statement": (
                "Given a 2D grid of 1s (land) and 0s (water), count the number of islands.\n"
                "An island is a group of 1s connected horizontally or vertically.\n"
                "Read with: import json; grid = json.loads(input())\n"
                "Example: [[1,1,0],[0,1,0],[0,0,1]] -> 2"
            ),
            "concept_tags": json.dumps(["graphs", "arrays", "recursion"]),
            "primary_concept": "graphs",
            "difficulty": "hard",
            "difficulty_score": 0.82,
            "prerequisite_concepts": json.dumps(["arrays", "recursion"]),
            "expected_complexity": "O(m*n)",
            "hidden_ratio": 0.5,
            "created_by": "faculty",
            "validated": True,
            "faculty_reviewed": True,
            "test_cases": json.dumps([
                _tc("[[1,1,0],[0,1,0],[0,0,1]]",     "2", False),
                _tc("[[1,1,1],[1,1,1],[1,1,1]]",     "1", False),
                _tc("[[0,0,0],[0,0,0]]",             "0", True),
                _tc("[[1,0,1],[0,1,0],[1,0,1]]",     "5", True),
            ]),
        },

        # ─────────────────────────────────────────────
        # P016 — Maximum Depth of Binary Tree | trees | hard
        # ─────────────────────────────────────────────
        {
            "problem_id": "P016",
            "title": "Maximum Depth of Binary Tree",
            "statement": (
                "Given a binary tree as a level-order JSON list (-1 = null node), "
                "print its maximum depth.\n"
                "Read with: import json; tree = json.loads(input())\n"
                "Example: [3,9,20,-1,-1,15,7] -> 3"
            ),
            "concept_tags": json.dumps(["trees", "recursion", "arrays"]),
            "primary_concept": "trees",
            "difficulty": "hard",
            "difficulty_score": 0.8,
            "prerequisite_concepts": json.dumps(["recursion", "arrays"]),
            "expected_complexity": "O(n)",
            "hidden_ratio": 0.5,
            "created_by": "faculty",
            "validated": True,
            "faculty_reviewed": True,
            "test_cases": json.dumps([
                _tc("[3,9,20,-1,-1,15,7]",   "3", False),
                _tc("[1]",                   "1", False),
                _tc("[1,2,3,4,5,-1,-1]",     "3", True),
                _tc("[]",                    "0", True),
            ]),
        },

        # ─────────────────────────────────────────────
        # P017 — Check Palindrome | strings | easy
        # ─────────────────────────────────────────────
        {
            "problem_id": "P017",
            "title": "Check Palindrome",
            "statement": (
                "Given a string, print True if it is a palindrome, False otherwise.\n"
                "Read with: s = input()\n"
                "Example: racecar -> True"
            ),
            "concept_tags": json.dumps(["strings", "loops"]),
            "primary_concept": "strings",
            "difficulty": "easy",
            "difficulty_score": 0.2,
            "prerequisite_concepts": json.dumps(["variables", "loops"]),
            "expected_complexity": "O(n)",
            "hidden_ratio": 0.5,
            "created_by": "faculty",
            "validated": True,
            "faculty_reviewed": True,
            "test_cases": json.dumps([
                _tc("racecar", "True",  False),
                _tc("hello",   "False", False),
                _tc("abba",    "True",  True),
                _tc("x",       "True",  True),
            ]),
        },

        # ─────────────────────────────────────────────
        # P018 — Longest Palindromic Substring Length | strings | medium
        # ─────────────────────────────────────────────
        {
            "problem_id": "P018",
            "title": "Longest Palindromic Substring Length",
            "statement": (
                "Given a string, print the length of its longest palindromic substring.\n"
                "Read with: s = input()\n"
                "Example: babad -> 3 (bab or aba)"
            ),
            "concept_tags": json.dumps(["strings", "dynamic_prog", "loops"]),
            "primary_concept": "strings",
            "difficulty": "medium",
            "difficulty_score": 0.6,
            "prerequisite_concepts": json.dumps(["strings", "loops"]),
            "expected_complexity": "O(n^2)",
            "hidden_ratio": 0.5,
            "created_by": "faculty",
            "validated": True,
            "faculty_reviewed": True,
            "test_cases": json.dumps([
                _tc("babad",   "3", False),
                _tc("cbbd",    "2", False),
                _tc("racecar", "7", True),
                _tc("a",       "1", True),
            ]),
        },

        # ─────────────────────────────────────────────
        # P019 — Bubble Sort | sorting | medium
        # ─────────────────────────────────────────────
        {
            "problem_id": "P019",
            "title": "Bubble Sort",
            "statement": (
                "Implement bubble sort. Print the sorted list.\n"
                "Read with: import json; nums = json.loads(input())\n"
                "Example: [64,34,25,12,22,11,90] -> [11, 12, 22, 25, 34, 64, 90]"
            ),
            "concept_tags": json.dumps(["sorting", "arrays", "loops"]),
            "primary_concept": "sorting",
            "difficulty": "medium",
            "difficulty_score": 0.6,
            "prerequisite_concepts": json.dumps(["arrays", "loops"]),
            "expected_complexity": "O(n^2)",
            "hidden_ratio": 0.5,
            "created_by": "faculty",
            "validated": True,
            "faculty_reviewed": True,
            "test_cases": json.dumps([
                _tc("[64,34,25,12,22,11,90]", "[11, 12, 22, 25, 34, 64, 90]", False),
                _tc("[5,1,4,2,8]",            "[1, 2, 4, 5, 8]",             False),
                _tc("[]",                     "[]",                           True),
                _tc("[3,-1,0,5,-2]",          "[-2, -1, 0, 3, 5]",           True),
            ]),
        },

        # ─────────────────────────────────────────────
        # P020 — Quick Sort | sorting | hard
        # ─────────────────────────────────────────────
        {
            "problem_id": "P020",
            "title": "Quick Sort",
            "statement": (
                "Implement quicksort. Print the sorted list.\n"
                "Read with: import json; nums = json.loads(input())\n"
                "Example: [3,6,8,10,1,2,1] -> [1, 1, 2, 3, 6, 8, 10]"
            ),
            "concept_tags": json.dumps(["sorting", "arrays", "recursion"]),
            "primary_concept": "sorting",
            "difficulty": "hard",
            "difficulty_score": 0.82,
            "prerequisite_concepts": json.dumps(["sorting", "arrays", "recursion"]),
            "expected_complexity": "O(n log n)",
            "hidden_ratio": 0.5,
            "created_by": "faculty",
            "validated": True,
            "faculty_reviewed": True,
            "test_cases": json.dumps([
                _tc("[3,6,8,10,1,2,1]",   "[1, 1, 2, 3, 6, 8, 10]",    False),
                _tc("[1]",                 "[1]",                        False),
                _tc("[-5,2,0,-1,3]",       "[-5, -1, 0, 2, 3]",         True),
                _tc("[9,8,7,6,5,4,3,2,1]", "[1, 2, 3, 4, 5, 6, 7, 8, 9]", True),
            ]),
        },
    ]
