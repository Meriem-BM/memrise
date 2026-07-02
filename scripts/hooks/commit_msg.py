from __future__ import annotations

import re
import sys
from pathlib import Path

COMMIT_RE = re.compile(
    r"^(build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)"
    r"(\([a-z0-9._-]+\))?!?: .{1,100}$"
)


def legacy_tokens() -> tuple[str, ...]:
    agent = "agent"
    memory = "memory"
    return (
        f"{agent}-{memory}",
        f"{agent}_{memory}",
        f"{agent}_{memory}_api",
        f"{agent}_{memory}_worker",
        f"@{agent}-{memory}",
        "Agent " + "Memory",
    )


def valid_special_subject(subject: str) -> bool:
    return subject.startswith(("Merge ", "Revert ", "fixup! ", "squash! "))


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: commit_msg.py <commit-msg-file>", file=sys.stderr)
        return 2

    message = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
    subject = next((line.strip() for line in message if line.strip()), "")
    if not subject:
        print("Commit message subject is empty.", file=sys.stderr)
        return 1

    for token in legacy_tokens():
        if token in "\n".join(message):
            print(f"Commit message contains legacy name {token!r}.", file=sys.stderr)
            return 1

    if valid_special_subject(subject):
        return 0

    if not COMMIT_RE.match(subject):
        print(
            "Commit subject must follow Conventional Commits, for example "
            "'feat(api): add retrieval endpoint'.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
