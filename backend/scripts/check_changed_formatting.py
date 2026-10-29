"""Check Black formatting on changed Python lines without reformatting legacy files."""

from __future__ import annotations

import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def changed_ranges(base: str, head: str) -> dict[str, list[tuple[int, int]]]:
    repo = Path(__file__).resolve().parents[2]
    if base == "0" * len(base):
        base = EMPTY_TREE

    command = ["git", "diff", "--no-ext-diff", "--unified=0", base]
    if head != "WORKTREE":
        command.append(head)
    command.extend(["--", "backend"])
    diff = subprocess.run(
        command,
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    output: dict[str, list[tuple[int, int]]] = defaultdict(list)
    current_file: str | None = None
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
            if not current_file.endswith(".py"):
                current_file = None
        elif line.startswith("+++ "):
            current_file = None
        elif current_file and line.startswith("@@"):
            match = HUNK.match(line)
            if not match:
                continue
            start = int(match.group(1))
            count = int(match.group(2) or "1")
            if count:
                output[current_file].append((start, start + count - 1))

    return {path: _merge_ranges(ranges) for path, ranges in output.items()}


def _merge_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def main() -> int:
    arguments = sys.argv[1:]
    fix = "--fix" in arguments
    if fix:
        arguments.remove("--fix")
    if len(arguments) not in (1, 2):
        print(
            "usage: check_changed_formatting.py BASE_SHA [HEAD_SHA|WORKTREE] [--fix]",
            file=sys.stderr,
        )
        return 2

    base = arguments[0]
    head = arguments[1] if len(arguments) == 2 else "WORKTREE"
    repo = Path(__file__).resolve().parents[2]
    ranges_by_file = changed_ranges(base, head)
    if not ranges_by_file:
        print("No changed Python lines to format-check.")
        return 0

    failed = False
    for relative_path, ranges in sorted(ranges_by_file.items()):
        path = repo / relative_path
        if not path.is_file():
            continue
        command = [sys.executable, "-m", "black"]
        if not fix:
            command.extend(["--check", "--diff"])
        command.extend(f"--line-ranges={start}-{end}" for start, end in ranges)
        command.append(str(path))
        result = subprocess.run(command, cwd=repo / "backend", check=False)
        failed |= result.returncode != 0

    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
