#!/usr/bin/env python3
"""Fail closed when a publishable system tree contains private material."""

import argparse
from pathlib import Path
import re

BLOCKED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".zip", ".docx", ".xlsx", ".pptx", ".html"}
BLOCKED_PARTS = {"sources", "outputs", "lessons", "records", "history", "archive"}
WHITELIST_PREFIXES = ("assets/ui-kit",)
ABSOLUTE_PATHS = (
    re.compile("/" + "Users/" + r"[^/\s]+/"),
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
    errors = []
    for path in system.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(system)
        if ".git" in relative.parts or "__pycache__" in relative.parts:
            continue
        if BLOCKED_PARTS.intersection(relative.parts):
            errors.append(f"private project directory: {relative}")
            continue
        if str(relative).startswith(WHITELIST_PREFIXES):
            continue
        if path.suffix.lower() in BLOCKED_SUFFIXES:
            errors.append(f"blocked file type: {relative}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"non-text file: {relative}")
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
