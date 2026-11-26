"""Conventional Commit validator for the commit-msg Git hook."""

from __future__ import annotations

import re
import sys
from pathlib import Path

PATTERN = re.compile(
    r"^(feat|fix|docs|chore|refactor|test|ci|build|perf|revert)"
    r"(\([a-z0-9._/-]+\))?!?: .{1,72}$"
)
ALLOWED = re.compile(r"^(Merge |Revert |Initial commit|Bump |chore\(gitops\):)")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_commit_message.py <commit-message-file>", file=sys.stderr)
        return 2
    subject = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()[0]
    if PATTERN.match(subject) or ALLOWED.match(subject):
        return 0
    print("Commit subject must use Conventional Commits, e.g.:", file=sys.stderr)
    print("  feat(api): add task filtering", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
