# sandbox/executor.py
# AdaptLab — Runs student code in a subprocess with timeout + memory limits.
# Returns ExecutionResult dataclass. No LLM involved.
# Imports from: utils/constants.py, utils/logger.py

import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field

from utils.constants import SANDBOX_MEMORY_MB, SANDBOX_TIMEOUT_SEC
from utils.logger import get_logger

log = get_logger("sandbox.executor")


# ─────────────────────────────────────────────
# Output contract
# ─────────────────────────────────────────────

@dataclass
class ExecutionResult:
    compiled:           bool
    passed_visible:     int
    total_visible:      int
    passed_hidden:      int
    total_hidden:       int
    pass_rate:          float          # all test cases combined (incl. hidden)
    visible_pass_rate:  float
    hidden_pass_rate:   float
    runtime_error:      bool
    timeout:            bool
    execution_time_ms:  int
    stderr:             str
    visible_results:    list = field(default_factory=list)
    # [{input, expected, got, passed}] — visible only, hidden never included
    test_outputs:       list = field(default_factory=list)
    # All test case stdout strings in order (visible + hidden)
    test_results:       list = field(default_factory=list)
    # All test case pass/fail booleans in order (visible + hidden)


# ─────────────────────────────────────────────
# Memory limiter (Linux only — silently skipped on other OS)
# ─────────────────────────────────────────────

def _make_preexec(memory_mb: int):
    """Returns a preexec_fn that sets virtual memory limit via resource module."""
    import platform
    if platform.system() == "Windows":
        return None   # preexec_fn is not supported on Windows
    def _set_limits():
        try:
            import resource
            limit_bytes = memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
        except Exception:
            pass  # unsupported — skip silently
    return _set_limits


# ─────────────────────────────────────────────
# Core execution helper — runs code against ONE test case
# ─────────────────────────────────────────────

def _run_single(
    code_file: str,
    stdin_data: str,
    timeout_sec: int,
    memory_mb: int,
) -> tuple[str, str, bool, bool, int]:
    """
    Returns: (stdout, stderr, timed_out, runtime_error, elapsed_ms)
    """
    start = time.monotonic()
    try:
        preexec = _make_preexec(memory_mb)
        run_kwargs = dict(
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        if preexec is not None:
            run_kwargs["preexec_fn"] = preexec
        result = subprocess.run(
            [sys.executable, code_file],
            **run_kwargs,
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        runtime_err = result.returncode != 0
        return result.stdout, result.stderr, False, runtime_err, elapsed_ms

    except subprocess.TimeoutExpired:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return "", "TimeoutExpired", True, False, elapsed_ms

    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return "", str(exc), False, True, elapsed_ms


# ─────────────────────────────────────────────
# Syntax-check helper — compile without running
# ─────────────────────────────────────────────

def _check_syntax(code: str) -> tuple[bool, str]:
    """Returns (compiled_ok, stderr_snippet)."""
    try:
        compile(code, "<student>", "exec")
        return True, ""
    except SyntaxError as exc:
        return False, f"SyntaxError: {exc}"


# ─────────────────────────────────────────────
# Public interface
# ─────────────────────────────────────────────

def run_code(
    student_code: str,
    test_cases: list[dict],
    language: str = "python",
) -> ExecutionResult:
    """
    Executes student_code against all test cases.

    test_cases: list of dicts with keys:
        - input  : str  (stdin to feed the process)
        - output : str  (expected stdout)
        - hidden : bool (True = hidden, excluded from visible_results)
    """
    if language != "python":
        log.warning("unsupported_language", language=language)
        return _zero_result(compiled=False, stderr=f"Unsupported language: {language}")

    # ── Step 1: Syntax check ──────────────────
    compiled, syntax_err = _check_syntax(student_code)
    if not compiled:
        log.info("syntax_error_detected", error=syntax_err[:200])
        return _zero_result(compiled=False, stderr=syntax_err)

    # ── Step 2: Write code to temp file ───────
    tmp_file = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(student_code)
            tmp_file = f.name

        # ── Step 3: Run each test case ────────
        passed_visible  = 0
        total_visible   = 0
        passed_hidden   = 0
        total_hidden    = 0
        visible_results = []
        all_test_outputs  = []    # stdout for every test case in order
        all_test_results  = []    # pass/fail for every test case in order
        total_elapsed   = 0
        timed_out       = False
        had_runtime_err = False
        last_stderr     = ""

        for tc in test_cases:
            stdin_data  = str(tc.get("input", ""))
            expected    = str(tc.get("output", "")).strip()
            is_hidden   = bool(tc.get("hidden", False))

            stdout, stderr, tc_timeout, tc_runtime_err, elapsed_ms = _run_single(
                code_file=tmp_file,
                stdin_data=stdin_data,
                timeout_sec=SANDBOX_TIMEOUT_SEC,
                memory_mb=SANDBOX_MEMORY_MB,
            )

            total_elapsed += elapsed_ms
            if tc_timeout:
                timed_out = True
            if tc_runtime_err:
                had_runtime_err = True
            if stderr:
                last_stderr = stderr

            got     = stdout.strip()
            passed  = (got == expected) and not tc_timeout and not tc_runtime_err

            # Track ALL test case results in order (visible + hidden)
            all_test_outputs.append(got if not tc_timeout else "<timeout>")
            all_test_results.append(passed)

            if is_hidden:
                total_hidden += 1
                if passed:
                    passed_hidden += 1
            else:
                total_visible += 1
                if passed:
                    passed_visible += 1
                # Hidden test results are NEVER appended to visible_results
                visible_results.append({
                    "input":    stdin_data,
                    "expected": expected,
                    "got":      got if not tc_timeout else "<timeout>",
                    "passed":   passed,
                })

        # ── Step 4: Compute rates ─────────────
        total_all    = total_visible + total_hidden
        passed_all   = passed_visible + passed_hidden

        pass_rate         = _safe_rate(passed_all, total_all)
        visible_pass_rate = _safe_rate(passed_visible, total_visible)
        hidden_pass_rate  = _safe_rate(passed_hidden, total_hidden)

        log.info(
            "execution_complete",
            pass_rate=pass_rate,
            visible=f"{passed_visible}/{total_visible}",
            hidden=f"{passed_hidden}/{total_hidden}",
            timed_out=timed_out,
            runtime_error=had_runtime_err,
            elapsed_ms=total_elapsed,
        )

        return ExecutionResult(
            compiled=True,
            passed_visible=passed_visible,
            total_visible=total_visible,
            passed_hidden=passed_hidden,
            total_hidden=total_hidden,
            pass_rate=pass_rate,
            visible_pass_rate=visible_pass_rate,
            hidden_pass_rate=hidden_pass_rate,
            runtime_error=had_runtime_err,
            timeout=timed_out,
            execution_time_ms=total_elapsed,
            stderr=last_stderr[:500],     # cap stderr to avoid bloat
            visible_results=visible_results,
            test_outputs=all_test_outputs,
            test_results=all_test_results,
        )

    finally:
        # ── Step 5: Clean up temp file ────────
        if tmp_file and os.path.exists(tmp_file):
            try:
                os.unlink(tmp_file)
            except OSError:
                pass


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _safe_rate(passed: int, total: int) -> float:
    """Returns 0.0 if total is zero — avoids ZeroDivisionError."""
    return round(passed / total, 4) if total > 0 else 0.0


def _zero_result(compiled: bool, stderr: str) -> ExecutionResult:
    """Returns an all-zero result for syntax errors and unsupported languages."""
    return ExecutionResult(
        compiled=compiled,
        passed_visible=0,
        total_visible=0,
        passed_hidden=0,
        total_hidden=0,
        pass_rate=0.0,
        visible_pass_rate=0.0,
        hidden_pass_rate=0.0,
        runtime_error=False,
        timeout=False,
        execution_time_ms=0,
        stderr=stderr,
        visible_results=[],
    )
