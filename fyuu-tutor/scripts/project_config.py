#!/usr/bin/env python3
"""Shared TOML loading and project path resolution."""

from pathlib import Path
import re
import tomllib

SCHEMA_VERSION = 3
PIPELINES = {"capability", "certification", "language"}
REQUIRED_FILES = ("project.toml", "pipeline.toml", "MISSION.md", "NOTES.md", "STATUS.md")
REQUIRED_PATHS = ("sources", "lessons", "reference", "records", "history", "profile")


def load_toml(path):
    with Path(path).open("rb") as handle:
        return tomllib.load(handle)


def load_project(project):
    root = Path(project).expanduser().resolve()
    config = load_toml(root / "project.toml")
    pipeline = load_toml(root / "pipeline.toml")
    return root, config, pipeline


def resolve_path(root, config, key):
    value = config["paths"][key]
    path = Path(value)
    if path.is_absolute():
        raise ValueError(f"paths.{key} must be relative: {value}")
    return (root / path).resolve()


def resolve_child(base, value, label="path"):
    base = Path(base).resolve()
    path = Path(value)
    if path.is_absolute():
        raise ValueError(f"{label} must be relative: {value}")
    resolved = (base / path).resolve()
    if resolved != base and base not in resolved.parents:
        raise ValueError(f"{label} escapes {base}: {value}")
    return resolved


def validate_config(root, config, pipeline):
    errors = []
    if config.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    pipeline_id = config.get("pipeline")
    if pipeline_id not in PIPELINES:
        errors.append(f"pipeline must be one of {sorted(PIPELINES)}")
    for key in ("project_id", "display_name", "content_language"):
        if not config.get(key):
            errors.append(f"missing {key}")
    paths = config.get("paths", {})
    for key in REQUIRED_PATHS:
        if not paths.get(key):
            errors.append(f"missing paths.{key}")
    if pipeline.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"pipeline.toml schema_version must be {SCHEMA_VERSION}")
    if pipeline_id and pipeline_id not in pipeline:
        errors.append(f"pipeline.toml missing [{pipeline_id}] section")
    for name in REQUIRED_FILES:
        if not (root / name).is_file():
            errors.append(f"missing {name}")
    return errors


def status_value(text, field, missing=None):
    """Extract a value from a STATUS.md markdown table row."""
    match = re.search(rf"^\|\s*{re.escape(field)}\s*\|\s*(.*?)\s*\|\s*$", text, re.MULTILINE)
    return match.group(1) if match else missing
