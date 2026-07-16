#!/usr/bin/env python3
"""Claim or release a project through its canonical STATUS.md table."""

import argparse
import datetime
from pathlib import Path
import re


def value(text, field):
    match = re.search(rf"^\|\s*{re.escape(field)}\s*\|\s*(.*?)\s*\|\s*$", text, re.MULTILINE)
    if not match:
        raise SystemExit(f"STATUS.md missing field: {field}")
    return match.group(1)


def replace(text, field, new_value):
    pattern = rf"^(\|\s*{re.escape(field)}\s*\|)\s*.*?\s*(\|\s*)$"
    return re.sub(pattern, rf"\1 {new_value} \2", text, count=1, flags=re.MULTILINE)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--action", required=True, choices=("claim", "release"))
    parser.add_argument("--owner", required=True)
    parser.add_argument("--task")
    parser.add_argument("--next-step")
    args = parser.parse_args()

    status_path = Path(args.project).expanduser().resolve() / "STATUS.md"
    text = status_path.read_text(encoding="utf-8")
    state = value(text, "State")
    current_owner = value(text, "Owner")
    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")

    if args.action == "claim":
        if state != "idle":
            raise SystemExit(f"cannot claim: status is {state}, owner is {current_owner}")
        if not args.task:
            raise SystemExit("--task is required when claiming")
        updates = {"State": "in_progress", "Owner": args.owner, "Claimed at": now, "Updated at": now, "Next action": args.task}
    else:
        if state != "in_progress" or current_owner != args.owner:
            raise SystemExit(f"cannot release: status is {state}, owner is {current_owner}")
        updates = {"State": "idle", "Owner": "—", "Claimed at": "—", "Updated at": now}
        if args.next_step:
            updates["Next action"] = args.next_step

    for field, new_value in updates.items():
        text = replace(text, field, new_value)
    status_path.write_text(text, encoding="utf-8")
    print(f"OK {args.action}: {status_path}")


if __name__ == "__main__":
    main()
