#!/usr/bin/env python3
"""Create an empty private learning project from bundled templates."""

import argparse
import json
from pathlib import Path
import re
import shutil

PIPELINES = ("capability", "certification", "language")


def toml_text(project_id, display_name, pipeline, content_language, profile):
    return f'''schema_version = 3
project_id = {json.dumps(project_id, ensure_ascii=False)}
display_name = {json.dumps(display_name, ensure_ascii=False)}
pipeline = {json.dumps(pipeline)}
content_language = {json.dumps(content_language)}

[paths]
sources = "sources"
lessons = "outputs/lessons"
reference = "outputs/reference"
records = "records"
history = "history"
profile = {json.dumps(profile, ensure_ascii=False)}
'''


def pipeline_text(pipeline):
    return f'''schema_version = 3

[{pipeline}]
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--pipeline", required=True, choices=PIPELINES)
    parser.add_argument("--content-language", default="en")
    parser.add_argument("--profile", default="../../profile/USER_PROFILE.md")
    parser.add_argument("--ui-kit", action="store_true", help="install UI v2 kit (CSS, JS, templates, spec, validator)")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", args.project_id):
        raise SystemExit("--project-id must use lowercase letters, digits, and hyphens")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*", args.content_language):
        raise SystemExit("--content-language must be a language tag such as en or zh-CN")
    if Path(args.profile).is_absolute():
        raise SystemExit("--profile must be relative to the project directory")
    projects_root = Path(args.root).expanduser().resolve()
    root = projects_root / args.project_id
    if root.exists():
        raise SystemExit(f"project already exists: {root}")
    for relative in ("sources", "outputs/lessons", "outputs/reference", "records", "history"):
        (root / relative).mkdir(parents=True, exist_ok=True)
    templates = Path(__file__).resolve().parent.parent / "assets" / "project-template"
    for name in ("MISSION.md", "NOTES.md", "STATUS.md"):
        shutil.copy2(templates / name, root / name)
    if args.pipeline == "certification":
        shutil.copy2(templates / "CURRICULUM.md", root / "CURRICULUM.md")
        shutil.copy2(templates / "SOURCE-MAP.md", root / "sources" / "SOURCE-MAP.md")
    (root / "project.toml").write_text(
        toml_text(args.project_id, args.display_name, args.pipeline, args.content_language, args.profile),
        encoding="utf-8",
    )
    (root / "pipeline.toml").write_text(pipeline_text(args.pipeline), encoding="utf-8")
    profile = (root / args.profile).resolve()
    if not profile.exists():
        profile.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(templates / "USER_PROFILE.md", profile)
    if args.ui_kit:
        import sync_ui_kit
        sync_ui_kit.install(root)
        shutil.copy2(Path(__file__).resolve().parent / "validate_lesson_ui.py", root / "tools" / "validate_lesson_ui.py")
    print(root)


if __name__ == "__main__":
    main()
