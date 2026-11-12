#!/usr/bin/env python3
"""Fail if the tree contains an email address that is not on the allowlist.

This repository is published. A personal address must never end up in the
source, the docs or a page of the site: contact goes through channels that
do not reveal an address (GitHub issues and private vulnerability reporting,
a contact form). The check runs in CI on every push and on the publication
tree before anything reaches the public repository.

Allowed without further ado: reserved example domains (example.org/.com/.net,
any name under the .example TLD). Every other address must be listed in
ALLOWED below, deliberately and one by one. Adding a real person's address
there is never the fix: remove the address instead.

    python3 .github/scripts/check_public_tree.py [root]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ADDRESS = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# Reserved for documentation and tests (RFC 2606, RFC 6761).
EXAMPLE_SUFFIXES = ("example.org", "example.com", "example.net", ".example")

# Role and service addresses, placeholders and test fixtures. Lower case.
ALLOWED = {
    "no-reply@kollepedia.se",  # the hosted instance's sender address
    "noreply@linderagroup.com",  # committer identity of the publish workflow
    "noreply@anthropic.com",  # Co-Authored-By trailer in CLAUDE.md
    "git@github.com",  # SSH remote
    "namn@exempel.se",  # placeholder in a form field
    "no-reply@example.se",  # placeholder sender in the environment template
    "pass@smtp-relay.brevo.com",  # userinfo of an SMTP URL in tests
    "skum@mailinator.com",  # disposable-address fixtures
    "ny@yopmail.com",
}
# GitHub's own privacy addresses (<id>+<login>@users.noreply.github.com).
ALLOWED_DOMAINS = {"users.noreply.github.com"}

SKIP_DIRS = {
    ".git",
    ".claude",
    ".design-sync",
    ".remember",
    ".obsidian",
    "node_modules",
    ".venv",
    ".svelte-kit",
    "build",
    "data",
    "test-results",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
}
SKIP_FILES = {
    "package-lock.json",
    "uv.lock",
    ".env",
    ".env.local",
    ".env.staging",
    ".env.production",
}


def allowed(address: str) -> bool:
    address = address.lower()
    domain = address.rsplit("@", 1)[1]
    if address in ALLOWED or domain in ALLOWED_DOMAINS:
        return True
    return any(
        domain == s.lstrip(".") or domain.endswith(s if s.startswith(".") else "." + s)
        for s in EXAMPLE_SUFFIXES
    )


def scan(root: Path) -> list[str]:
    findings: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name in SKIP_FILES:
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable: not prose
        for number, line in enumerate(text.splitlines(), start=1):
            for match in ADDRESS.finditer(line):
                if not allowed(match.group(0)):
                    findings.append(
                        f"{path.relative_to(root)}:{number}: {match.group(0)}"
                    )
    return findings


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    findings = scan(root)
    if findings:
        print("Email addresses that are not on the allowlist:")
        print("\n".join("  " + finding for finding in findings))
        print(
            "Remove them; contact goes through GitHub or a contact form, never a personal address."
        )
        return 1
    print(f"No unlisted email addresses under {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
