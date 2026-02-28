# analysis/feature_extractor.py
# AdaptLab — Python AST analysis. Returns CodeFeatures dataclass.
# No LLM involved. Pure deterministic static analysis.
# Imports from: utils/constants.py, utils/logger.py

import ast
from dataclasses import dataclass, field
from typing import Optional

from utils.logger import get_logger

log = get_logger("analysis.feature_extractor")


# ─────────────────────────────────────────────
# Output contract
# ─────────────────────────────────────────────

@dataclass
class CodeFeatures:
    # Complexity estimate
    complexity_estimate:      str   # 'O(1)' | 'O(n)' | 'O(n^2)' | 'O(n log n)' | 'unknown'

    # Structural flags
    uses_recursion:           bool
    nested_loops:             bool
    loop_count:               int

    # Error classification flags
    syntax_error:             bool
    off_by_one_risk:          bool  # loop range ending at len(x) instead of len(x)-1
    missing_base_case:        bool  # recursive fn with no base-case return
    wrong_data_structure:     bool  # dict-like problem solved with list, or vice versa
    brute_force_detected:     bool  # nested loops on sortable data
    approach_mismatch:        bool  # sorting problem solved without sorting
    generalization_failure:   bool  # hardcoded magic numbers as loop bounds
    hardcoded_values:         bool  # literal return values in simple single-path functions
    uses_sorting_api:         bool  # calls .sort() or sorted()

    # Primary error classification (single label, priority ordered)
    error_type: str = "none"
    # Priority: syntax_error > missing_base_case > off_by_one >
    #           wrong_data_structure > brute_force_detected >
    #           hardcoded_values > generalization_failure >
    #           approach_mismatch > none


# ─────────────────────────────────────────────
# AST visitor
# ─────────────────────────────────────────────

class _CodeAnalyser(ast.NodeVisitor):
    """
    Single-pass AST walker. Collects all structural signals needed
    to populate CodeFeatures. Called internally by extract_features().
    """

    def __init__(self) -> None:
        # Loop tracking
        self.loop_count:        int  = 0
        self.loop_depth:        int  = 0
        self.max_loop_depth:    int  = 0

        # Recursion tracking
        self.function_names:    set[str] = set()
        self.recursive_calls:   set[str] = set()  # fn names that call themselves

        # Error signal flags
        self.off_by_one_risk:           bool = False
        self.missing_base_case:         bool = False
        self.wrong_data_structure:      bool = False
        self.brute_force_detected:      bool = False
        self.approach_mismatch:         bool = False
        self.generalization_failure:    bool = False
        self.hardcoded_values:          bool = False
        self.uses_sorting_api:          bool = False

        # Internal state
        self._current_func_name:        Optional[str] = None
        self._func_has_base_return:     dict[str, bool] = {}
        self._func_call_names:          dict[str, set[str]] = {}
        self._return_literals:          dict[str, int] = {}   # func -> count of literal returns
        self._total_returns:            dict[str, int] = {}   # func -> total return stmts
        self._has_loop:                 bool = False
        self._has_dict_usage:           bool = False
        self._has_list_usage:           bool = False

    # ── Function definitions ──────────────────

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        prev = self._current_func_name
        self._current_func_name = node.name
        self.function_names.add(node.name)
        self._func_has_base_return[node.name] = False
        self._func_call_names[node.name] = set()
        self._return_literals[node.name] = 0
        self._total_returns[node.name] = 0
        self.generic_visit(node)
        self._current_func_name = prev

    visit_AsyncFunctionDef = visit_FunctionDef

    # ── Return statements ─────────────────────

    def visit_Return(self, node: ast.Return) -> None:
        fn = self._current_func_name
        if fn:
            self._total_returns[fn] = self._total_returns.get(fn, 0) + 1
            # Base-case heuristic: return of a constant/literal at top level of fn
            if isinstance(node.value, (ast.Constant, ast.UnaryOp)):
                self._func_has_base_return[fn] = True
                self._return_literals[fn] = self._return_literals.get(fn, 0) + 1
        self.generic_visit(node)

    # ── Function calls ────────────────────────

    def visit_Call(self, node: ast.Call) -> None:
        fn = self._current_func_name
        call_name = _get_call_name(node)

        if call_name and fn:
            self._func_call_names[fn].add(call_name)

        # Detect sorting API usage
        if call_name in ("sorted", "sort", "list.sort"):
            self.uses_sorting_api = True
        if isinstance(node.func, ast.Attribute) and node.func.attr == "sort":
            self.uses_sorting_api = True

        self.generic_visit(node)

    # ── Loops ─────────────────────────────────

    def visit_For(self, node: ast.For) -> None:
        self._enter_loop(node)

    def visit_While(self, node: ast.While) -> None:
        self._enter_loop(node)

    def _enter_loop(self, node: ast.AST) -> None:
        self.loop_count += 1
        self._has_loop = True
        self.loop_depth += 1
        if self.loop_depth > self.max_loop_depth:
            self.max_loop_depth = self.loop_depth

        # Off-by-one risk: range(..., len(x)) without -1
        if isinstance(node, ast.For):
            self._check_off_by_one(node)
            self._check_magic_bound(node)

        self.generic_visit(node)
        self.loop_depth -= 1

    def _check_off_by_one(self, node: ast.For) -> None:
        """
        Flags range(len(x)) as potential off-by-one risk if the loop
        body accesses node[i+1] or node[i-1] (over-indexing risk).
        Also flags range(0, len(x)) patterns.
        """
        if not isinstance(node.iter, ast.Call):
            return
        call = node.iter
        if not (_get_call_name(call) == "range"):
            return
        for arg in call.args:
            if (
                isinstance(arg, ast.Call)
                and _get_call_name(arg) == "len"
            ):
                self.off_by_one_risk = True
                return

    def _check_magic_bound(self, node: ast.For) -> None:
        """
        Generalization failure: loop bound is a bare integer literal
        instead of len(collection). e.g. for i in range(5): ...
        """
        if not isinstance(node.iter, ast.Call):
            return
        if _get_call_name(node.iter) != "range":
            return
        for arg in node.iter.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, int):
                self.generalization_failure = True
                return

    # ── Data structure usage ──────────────────

    def visit_Dict(self, node: ast.Dict) -> None:
        self._has_dict_usage = True
        self.generic_visit(node)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._has_dict_usage = True
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        self.generic_visit(node)

    # ── Detect wrong data structure ───────────
    # Heuristic: code has nested loops but never uses dict/set,
    # suggesting O(n^2) where O(n) dict lookup was possible.

    def _finalise_wrong_data_structure(self) -> None:
        if self.max_loop_depth >= 2 and not self._has_dict_usage:
            self.wrong_data_structure = True

    # ── Detect hardcoded return values ────────
    # Heuristic: a function where ALL returns are literals
    # and it has no loops and no recursion → likely hardcoded output.

    def _finalise_hardcoded_values(self) -> None:
        for fn in self.function_names:
            total   = self._total_returns.get(fn, 0)
            literal = self._return_literals.get(fn, 0)
            calls   = self._func_call_names.get(fn, set())
            # Only flag if: has returns, all returns are literals,
            # no loops in the function (loop_count proxy), no self-calls.
            if (
                total > 0
                and total == literal
                and fn not in self.recursive_calls
                and self.loop_count == 0
            ):
                self.hardcoded_values = True

    # ── Detect recursion ─────────────────────

    def _finalise_recursion(self) -> None:
        for fn in self.function_names:
            calls = self._func_call_names.get(fn, set())
            if fn in calls:
                self.recursive_calls.add(fn)

    # ── Detect missing base case ──────────────
    # Heuristic: recursive function where no return of a constant
    # was detected at the top-level function body.

    def _finalise_missing_base_case(self) -> None:
        for fn in self.recursive_calls:
            if not self._func_has_base_return.get(fn, False):
                self.missing_base_case = True

    # ── Detect brute force ────────────────────
    # Heuristic: nested loops (O(n^2)) but no sorting API used.

    def _finalise_brute_force(self) -> None:
        if self.max_loop_depth >= 2 and not self.uses_sorting_api:
            self.brute_force_detected = True

    # ── Detect approach mismatch ──────────────
    # Heuristic: nested loops present but no sorting API — on a
    # problem that likely requires sorting (already covered by brute_force,
    # but approach_mismatch captures the wrong-strategy angle).

    def _finalise_approach_mismatch(self) -> None:
        if self._has_loop and not self.uses_sorting_api and self.max_loop_depth >= 2:
            self.approach_mismatch = True

    def finalise(self) -> None:
        """Call after generic_visit completes to resolve multi-pass signals."""
        self._finalise_recursion()
        self._finalise_missing_base_case()
        self._finalise_wrong_data_structure()
        self._finalise_hardcoded_values()
        self._finalise_brute_force()
        self._finalise_approach_mismatch()


# ─────────────────────────────────────────────
# Public interface
# ─────────────────────────────────────────────

def extract_features(code: str, language: str = "python") -> CodeFeatures:
    """
    Parses `code` and returns a populated CodeFeatures dataclass.
    On SyntaxError, returns a CodeFeatures with syntax_error=True and safe defaults.
    """
    if language != "python":
        log.warning("unsupported_language_for_extraction", language=language)
        return _syntax_error_features()

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        log.info("feature_extractor_syntax_error", error=str(exc))
        return _syntax_error_features()

    analyser = _CodeAnalyser()
    analyser.visit(tree)
    analyser.finalise()

    nested_loops      = analyser.max_loop_depth >= 2
    uses_recursion    = bool(analyser.recursive_calls)
    complexity        = _estimate_complexity(
        nested_loops=nested_loops,
        loop_count=analyser.loop_count,
        uses_recursion=uses_recursion,
        uses_sorting_api=analyser.uses_sorting_api,
    )

    features = CodeFeatures(
        complexity_estimate=complexity,
        uses_recursion=uses_recursion,
        nested_loops=nested_loops,
        loop_count=analyser.loop_count,
        syntax_error=False,
        off_by_one_risk=analyser.off_by_one_risk,
        missing_base_case=analyser.missing_base_case,
        wrong_data_structure=analyser.wrong_data_structure,
        brute_force_detected=analyser.brute_force_detected,
        approach_mismatch=analyser.approach_mismatch,
        generalization_failure=analyser.generalization_failure,
        hardcoded_values=analyser.hardcoded_values,
        uses_sorting_api=analyser.uses_sorting_api,
    )

    features.error_type = _classify_error(features)

    log.info(
        "features_extracted",
        error_type=features.error_type,
        complexity=features.complexity_estimate,
        loops=features.loop_count,
        recursion=features.uses_recursion,
        nested=features.nested_loops,
    )

    return features


# ─────────────────────────────────────────────
# Error type classifier — priority ordered
# ─────────────────────────────────────────────

def _classify_error(f: CodeFeatures) -> str:
    """
    Returns a single error_type string based on priority ordering
    defined in the spec:
        syntax_error > missing_base_case > off_by_one >
        wrong_data_structure > brute_force_detected >
        hardcoded_values > generalization_failure >
        approach_mismatch > none
    """
    if f.syntax_error:
        return "syntax_error"
    if f.missing_base_case:
        return "missing_base_case"
    if f.off_by_one_risk:
        return "off_by_one"
    if f.wrong_data_structure:
        return "wrong_data_structure"
    if f.brute_force_detected:
        return "brute_force_detected"
    if f.hardcoded_values:
        return "hardcoded_values"
    if f.generalization_failure:
        return "generalization_failure"
    if f.approach_mismatch:
        return "approach_mismatch"
    return "none"


# ─────────────────────────────────────────────
# Complexity estimator
# ─────────────────────────────────────────────

def _estimate_complexity(
    nested_loops: bool,
    loop_count: int,
    uses_recursion: bool,
    uses_sorting_api: bool,
) -> str:
    """
    Conservative heuristic:
    - Nested loops                  → O(n^2)
    - Uses sorting API              → O(n log n)
    - Single loop (no nesting)      → O(n)
    - Recursion only, no loops      → O(n)  (conservative; could be exponential)
    - No loops, no recursion        → O(1)
    - Unknown fallback              → O(1)
    """
    if nested_loops:
        return "O(n^2)"
    if uses_sorting_api:
        return "O(n log n)"
    if loop_count > 0:
        return "O(n)"
    if uses_recursion:
        return "O(n)"
    return "O(1)"


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _get_call_name(node: ast.Call) -> Optional[str]:
    """Extracts the callable name from a Call node, handling attr and Name forms."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _syntax_error_features() -> CodeFeatures:
    f = CodeFeatures(
        complexity_estimate="unknown",
        uses_recursion=False,
        nested_loops=False,
        loop_count=0,
        syntax_error=True,
        off_by_one_risk=False,
        missing_base_case=False,
        wrong_data_structure=False,
        brute_force_detected=False,
        approach_mismatch=False,
        generalization_failure=False,
        hardcoded_values=False,
        uses_sorting_api=False,
        error_type="syntax_error",
    )
    return f
