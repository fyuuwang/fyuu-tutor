#!/usr/bin/env python3
"""Claim or release a project through its canonical STATUS.md table."""

import argparse
import datetime
from pathlib import Path
import re
import tempfile

import sys as _sys
_sys.dont_write_bytecode = True
_sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_config import status_value

STATUS_FIELDS = ("State", "Owner", "Claimed at", "Updated at", "Production progress", "Learning progress", "Next action", "Blockers")


def value(text, field):
    result = status_value(text, field)
    if result is None:
        raise SystemExit(f"STATUS.md missing field: {field}")
    return result


def replace(text, field, new_value):
    pattern = rf"^(\|\s*{re.escape(field)}\s*\|)\s*.*?\s*(\|\s*)$"
    return re.sub(
        pattern,
        lambda match: f"{match.group(1)} {new_value} {match.group(2)}",
        text,
        count=1,
        flags=re.MULTILINE,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--action", required=True, choices=("claim", "release"))
    parser.add_argument("--owner", required=True)
    parser.add_argument("--task")
    parser.add_argument("--next-step")
    args = parser.parse_args()

    args.owner = args.owner.strip()
    if not args.owner or args.owner == "—":
        raise SystemExit("--owner must identify a real agent")

    status_path = Path(args.project).expanduser().resolve() / "STATUS.md"
    status = status_path.read_text(encoding="utf-8")
    current = {field: value(status, field) for field in STATUS_FIELDS}
    now = datetime.datetime.now().astimezone().isoformat(timespec="minutes")
    if args.action == "claim":
        if args.task is None or not args.task.strip():
            raise SystemExit("--task is required for claim action")
        if current["State"] != "idle":
            raise SystemExit("claim requires STATUS.State to be idle")
        updates = {"State": "in_progress", "Owner": args.owner, "Claimed at": now, "Updated at": now, "Next action": args.task}
    else:
        if current["State"] != "in_progress":
            raise SystemExit("release requires STATUS.State to be in_progress")
        if current["Owner"] != args.owner:
            raise SystemExit("release requires the current STATUS.Owner")
        updates = {"State": "idle", "Owner": "—", "Claimed at": "—", "Updated at": now}
        if args.next_step is not None:
            updates["Next action"] = args.next_step

    # Reject dangerous input before writing
    for field, new_value in updates.items():
        if isinstance(new_value, str) and ("\n" in new_value or "\r" in new_value or "|" in new_value):
            raise SystemExit(f"STATUS.{field} must not contain newlines or pipe characters")

    new_status = status
    for field, new_value in updates.items():
        new_status = replace(new_status, field, new_value)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=status_path.parent, delete=False) as handle:
        handle.write(new_status)
        temp_path = Path(handle.name)
    temp_path.replace(status_path)
    print(f"OK {args.action}: {args.owner}")


if __name__ == "__main__":
    main()
