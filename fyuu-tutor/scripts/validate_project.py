#!/usr/bin/env python3
"""Validate a private learning project without changing it."""

import argparse
import datetime
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True

from project_config import REQUIRED_PATHS, load_project, resolve_child, resolve_path, status_value, validate_config

STATUS_FIELDS = ("State", "Owner", "Claimed at", "Updated at", "Production progress", "Learning progress", "Next action", "Blockers")
STATUS_STATES = {"idle", "in_progress", "blocked"}
CERTIFICATION_FIELDS = {
    "exam_date": str,
    "target_score": (int, float),
    "study_tracks": list,
    "practice_start": str,
    "question_answer_status": str,
    "authority_version": str,
    "authority_checked_on": str,
    "authority_review_due": str,
    "authority_url": str,
    "authority_source": str,
    "total_questions": int,
    "exam_minutes": int,
    "pretest_questions": int,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    root, config, pipeline = load_project(args.project)
    errors = validate_config(root, config, pipeline)
    if config.get("pipeline") == "certification":
        section = pipeline.get("certification", {})
        for field, expected_type in CERTIFICATION_FIELDS.items():
            value = section.get(field)
            if not isinstance(value, expected_type) or value in ("", []):
                errors.append(f"certification.{field} missing or invalid")
        dates = {}
        for field in ("exam_date", "practice_start", "authority_checked_on", "authority_review_due"):
            try:
                dates[field] = datetime.date.fromisoformat(section.get(field, ""))
            except (TypeError, ValueError):
                errors.append(f"certification.{field} must be YYYY-MM-DD")
        if dates.get("authority_review_due") and datetime.date.today() > dates["authority_review_due"]:
            errors.append("certification authority review is overdue")
        if not (root / "CURRICULUM.md").is_file():
            errors.append("certification project missing CURRICULUM.md")
        source_map = root / "sources" / "SOURCE-MAP.md"
        if not source_map.is_file():
            errors.append("certification project missing sources/SOURCE-MAP.md")
        try:
            authority = resolve_child(root / "sources", section.get("authority_source", ""), "certification.authority_source")
            if not authority.is_file():
                errors.append(f"certification authority source missing: {authority}")
        except ValueError as exc:
            errors.append(str(exc))
    if not errors:
        for key in REQUIRED_PATHS:
            try:
                path = resolve_path(root, config, key)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            if key != "profile" and path != root and root not in path.parents:
                errors.append(f"paths.{key} escapes project directory: {path}")
                continue
            if key != "profile" and not path.is_dir():
                errors.append(f"missing directory paths.{key}: {path}")
            if key == "profile" and not path.is_file():
                errors.append(f"missing profile: {path}")
    status_path = root / "STATUS.md"
    if status_path.is_file():
        try:
            status = status_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append("STATUS.md must be valid UTF-8")
        else:
            for field in STATUS_FIELDS:
                if status_value(status, field) is None:
                    errors.append(f"STATUS.md missing field: {field}")
            state = status_value(status, "State")
            if state and state not in STATUS_STATES:
                errors.append(f"STATUS.md invalid State: {state}")
            if state == "in_progress":
                for field in ("Owner", "Claimed at"):
                    if status_value(status, field) in (None, "", "—"):
                        errors.append(f"STATUS.md {field} required while in_progress")
            for field in ("Owner", "Next action", "Blockers"):
                val = status_value(status, field) or ""
                if isinstance(val, str) and ("\n" in val or "|" in val):
                    errors.append(f"STATUS.{field} must not contain newlines or pipe characters")
    if errors:
        for error in errors:
            print(f"ERROR {error}")
        raise SystemExit(1)
    print(f"OK {config['project_id']} -> {config['pipeline']}")


if __name__ == "__main__":
    main()
