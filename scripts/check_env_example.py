"""Scan source for environment variable usage and verify all are in .env.example."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


def find_env_vars_in_source(root: Path) -> set[str]:
    env_vars: set[str] = set()
    patterns = [
        re.compile(r'os\.(?:environ|getenv)\s*\(\s*["\']([A-Za-z_][A-Za-z0-9_]*)["\']'),
        re.compile(r'process\.env\.([A-Za-z_][A-Za-z0-9_]*)'),
    ]
    skip_dirs = {"node_modules", ".venv", ".next", ".git", "__pycache__", ".ruff_cache", ".pytest_cache"}

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for filename in filenames:
            if not filename.endswith((".py", ".ts", ".tsx", ".js", ".jsx")):
                continue
            file_path = Path(dirpath) / filename
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                for pattern in patterns:
                    for match in pattern.finditer(content):
                        env_vars.add(match.group(1))
            except (OSError, UnicodeDecodeError):
                continue

    return env_vars


def read_env_example(path: Path) -> set[str]:
    if not path.exists():
        return set()
    vars_in_example: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=', stripped)
        if match:
            vars_in_example.add(match.group(1))
    return vars_in_example


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    env_example = root / ".env.example"

    # Only scan our application code, not dependencies
    used_in_source: set[str] = set()
    for app_dir in ("backend", "frontend"):
        app_root = root / app_dir
        if app_root.exists():
            used_in_source |= find_env_vars_in_source(app_root)
    defined_in_example = read_env_example(env_example)

    missing = used_in_source - defined_in_example

    if missing:
        print(f"ERROR: {len(missing)} environment variable(s) referenced in source "
              f"are missing from .env.example:", file=sys.stderr)
        for var in sorted(missing):
            print(f"  - {var}", file=sys.stderr)
        print(f"\nAdd them to {env_example}", file=sys.stderr)
        return 1

    print(f"OK: All {len(used_in_source)} environment variable(s) referenced in source "
          f"are defined in .env.example")
    return 0


if __name__ == "__main__":
    sys.exit(main())
