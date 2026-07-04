"""Sandboxed code execution tool — Python and shell commands.

WARNING: This tool uses subprocess and should only be enabled in trusted
environments. No true sandboxing is applied.
"""
from __future__ import annotations
import os
import subprocess  # noqa: S404
import sys
import tempfile
import time
from typing import Any


_EXECUTION_TIMEOUT = 30
_MAX_OUTPUT_LENGTH = 50_000
_BLOCKED_PATTERNS = [
    "import os",
    "import subprocess",
    "import sys",
    "import shutil",
    "import signal",
    "__import__",
    "eval(",
    "exec(",
    "open(",
    "open(",
    "builtins",
]


def execute_python(
    code: str,
    timeout: int = _EXECUTION_TIMEOUT,
) -> dict[str, Any]:
    """Execute Python code in a subprocess and return the output.

    Args:
        code: Python source code to execute.
        timeout: Maximum execution time in seconds.

    Returns:
        Dict with keys: success, stdout, stderr, duration_ms, error.
    """
    if _is_dangerous(code):
        return {
            "success": False,
            "stdout": "",
            "stderr": "Code contains blocked patterns (os, subprocess, eval, etc.)",
            "duration_ms": 0,
        }

    start = time.time()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        tmp_path = f.name

    try:
        result = subprocess.run(  # noqa: S602
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            env={},
        )
        duration_ms = round((time.time() - start) * 1000, 2)
        stdout = result.stdout[-_MAX_OUTPUT_LENGTH:] if result.stdout else ""
        stderr = result.stderr[-_MAX_OUTPUT_LENGTH:] if result.stderr else ""

        return {
            "success": result.returncode == 0,
            "stdout": stdout,
            "stderr": stderr,
            "return_code": result.returncode,
            "duration_ms": duration_ms,
        }
    except subprocess.TimeoutExpired:
        duration_ms = round((time.time() - start) * 1000, 2)
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Execution timed out after {timeout}s",
            "duration_ms": duration_ms,
        }
    except Exception as e:
        duration_ms = round((time.time() - start) * 1000, 2)
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "duration_ms": duration_ms,
        }
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def execute_shell(
    command: str,
    timeout: int = _EXECUTION_TIMEOUT,
) -> dict[str, Any]:
    """Execute a shell command in a subprocess and return the output.

    Args:
        command: Shell command to execute.
        timeout: Maximum execution time in seconds.

    Returns:
        Dict with keys: success, stdout, stderr, duration_ms, error.
    """
    start = time.time()
    try:
        result = subprocess.run(  # noqa: S603
            ["sh", "-c", command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration_ms = round((time.time() - start) * 1000, 2)
        stdout = result.stdout[-_MAX_OUTPUT_LENGTH:] if result.stdout else ""
        stderr = result.stderr[-_MAX_OUTPUT_LENGTH:] if result.stderr else ""

        return {
            "success": result.returncode == 0,
            "stdout": stdout,
            "stderr": stderr,
            "return_code": result.returncode,
            "duration_ms": duration_ms,
        }
    except subprocess.TimeoutExpired:
        duration_ms = round((time.time() - start) * 1000, 2)
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Execution timed out after {timeout}s",
            "duration_ms": duration_ms,
        }
    except Exception as e:
        duration_ms = round((time.time() - start) * 1000, 2)
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "duration_ms": duration_ms,
        }


def _is_dangerous(code: str) -> bool:
    """Check code for dangerous patterns (basic static analysis)."""
    code_lower = code.lower()
    for pattern in _BLOCKED_PATTERNS:
        if pattern in code_lower:
            return True
    return False
