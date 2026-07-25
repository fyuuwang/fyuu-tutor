#!/usr/bin/env python3
"""Fail closed when a publishable system tree contains private material."""

import argparse
from pathlib import Path
import re

import subprocess

BLOCKED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".zip", ".docx", ".xlsx", ".pptx", ".html"}
BLOCKED_PARTS = {"sources", "outputs", "lessons", "records", "history", "archive"}
ABSOLUTE_PATHS = (
    re.compile("/" + "Users/" + r"[^/\s]+/"),
    re.compile("/" + "home/" + r"[^/\s]+/"),
    re.compile("/" + "private/" + r"[^/\s]+/"),
    re.compile(r"[A-Za-z]:\\" + "Users" + r"\\"),
)
WORKSPACE_REFERENCE = re.compile(r"(?:\.\./)+" + "work" + "space/" + r"|(?<![<\w-])" + "work" + "space/")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", required=True)
    parser.add_argument("--markers")
    args = parser.parse_args()
    system = Path(args.system).expanduser().resolve()
    markers = []
    if args.markers:
        markers = [line.strip() for line in Path(args.markers).read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]

    # Audit all files git knows about: tracked (cached) PLUS untracked-but-not-
    # ignored (others --exclude-standard). This ensures new scripts that haven't
    # been `git add`-ed yet are still checked, while .gitignore entries (e.g.
    # .omx/, __pycache__) remain excluded. In a non-git environment, fall back
    # to rglob with the same fail-closed semantics (no dir-name exemptions).
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", "."],
            cwd=str(system), capture_output=True, text=True, check=True,
        )
        visible = {p for p in result.stdout.splitlines() if p}
    except (subprocess.CalledProcessError, FileNotFoundError):
        visible = None

    errors = []
    for path in sorted(system.rglob("*")):
        # Reject symlinks BEFORE any resolve() -- external symlinks would
        # leak outside the repository and resolve() would skip them entirely.
        if path.is_symlink():
            try:
                rel = path.relative_to(system)
            except ValueError:
                rel = path
            errors.append(f"symlink rejected: {rel}")
            continue
        if not path.is_file():
            continue
        if visible is not None:
            try:
                rel_git = path.resolve().relative_to(system).as_posix()
            except ValueError:
                errors.append(f"external path rejected: {path}")
                continue
            if rel_git not in visible:
                continue
        relative = path.relative_to(system)
        if ".git" in relative.parts or "__pycache__" in relative.parts:
            continue
        if BLOCKED_PARTS.intersection(relative.parts):
            errors.append(f"private project directory: {relative}")
            continue
        if path.suffix.lower() in BLOCKED_SUFFIXES:
            if any(part in relative.parts for part in ("ui-kit",)):
                pass  # ui-kit HTML is allowed but content is still scanned
            else:
                errors.append(f"blocked file type: {relative}")
                continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"non-text file: {relative}")
            continue
        except OSError as e:
            errors.append(f"unreadable file: {relative}: {e}")
            continue
        for pattern in ABSOLUTE_PATHS:
            if pattern.search(text):
                errors.append(f"absolute path: {relative}")
                break
        if WORKSPACE_REFERENCE.search(text):
            errors.append(f"workspace reference: {relative}")
        for marker in markers:
            if marker in text:
                errors.append(f"private marker {marker!r}: {relative}")
    if errors:
        for error in errors:
            print(f"ERROR {error}")
        raise SystemExit(1)
    print(f"OK privacy audit: {system}")



if __name__ == "__main__":
    main()
