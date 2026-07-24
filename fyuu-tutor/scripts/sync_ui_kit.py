#!/usr/bin/env python3
"""Install, check, or upgrade the Fyuu Tutor UI kit in a learning project."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
KIT_DIR = SKILL_DIR / "assets" / "ui-kit"

# Files to sync: (source_relative_to_kit, dest_relative_to_project)
# lesson.css is NOT listed here — it is generated from the three CSS sources.
# This prevents desync: editing tokens.css without rebuilding lesson.css.
KIT_FILES = [
    ("assets/tokens.css", "outputs/assets/tokens.css"),
    ("assets/foundation.css", "outputs/assets/foundation.css"),
    ("assets/components.css", "outputs/assets/components.css"),
    ("assets/lesson.js", "outputs/assets/lesson.js"),
    ("templates/lesson.html", "outputs/templates/lesson.html"),
    ("templates/practice.html", "outputs/templates/practice.html"),
    ("templates/reference.html", "outputs/templates/reference.html"),
    ("templates/components.html", "outputs/templates/components.html"),
    ("templates/gallery.html", "outputs/ui/gallery.html"),
    ("ui-spec.json", "outputs/ui/ui-spec.json"),
    ("../../references/ui-contract.md", "UI-CONTRACT.md"),
]

MANIFEST_NAME = "outputs/ui/kit-manifest.json"
LESSON_CSS_KEY = "assets/lesson.css"
LESSON_CSS_DEST = "outputs/assets/lesson.css"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


CSS_HEADER = "/* Fyuu Tutor UI v2 - single entry point. Generated from tokens + foundation + components. */\n"


def build_lesson_css(kit_assets: Path) -> str:
    """Concatenate tokens.css + foundation.css + components.css into a single string."""
    parts = []
    for name in ("tokens.css", "foundation.css", "components.css"):
        src = kit_assets / name
        if not src.is_file():
            raise FileNotFoundError(f"CSS source missing: {name}")
        parts.append(src.read_text(encoding="utf-8").rstrip())
    return CSS_HEADER + "\n".join(parts) + "\n"


def kit_payloads() -> list[tuple[str, str, bytes]]:
    """Return every installed file from one canonical source map."""
    payloads = []
    for src_rel, dest_rel in KIT_FILES:
        src = KIT_DIR / src_rel
        if not src.is_file():
            raise FileNotFoundError(f"UI kit source missing: {src_rel}")
        payloads.append((src_rel, dest_rel, src.read_bytes()))
    payloads.append((
        LESSON_CSS_KEY,
        LESSON_CSS_DEST,
        build_lesson_css(KIT_DIR / "assets").encode(),
    ))
    return payloads


def build_manifest() -> dict:
    """Build manifest from current skill kit files."""
    return {
        "kit_version": "2",
        "files": {key: sha256_bytes(content) for key, _, content in kit_payloads()},
    }


def install(project: Path) -> int:
    dest_manifest = project / MANIFEST_NAME
    if dest_manifest.is_file():
        print(f"UI kit already installed in {project.name}. Use --upgrade to update.")
        return 1
    return do_copy(project, "install")


def do_copy(project: Path, action: str) -> int:
    payloads = kit_payloads()
    for _, dest_rel, content in payloads:
        dest = project / dest_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
    manifest = build_manifest()
    manifest_path = project / MANIFEST_NAME
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"OK {action}: {len(payloads)} files synced to {project.name}")
    return 0


def check(project: Path) -> int:
    manifest_path = project / MANIFEST_NAME
    if not manifest_path.is_file():
        print(f"FAIL: no kit-manifest.json in {project.name}. Run --install first.")
        return 1
    saved = json.loads(manifest_path.read_text())
    mismatches = []
    upgrades = []
    for key, dest_rel, content in kit_payloads():
        old_hash = saved.get("files", {}).get(key, "")
        expected_hash = sha256_bytes(content)
        dest = project / dest_rel
        if not dest.is_file():
            mismatches.append(f"missing: {dest.relative_to(project)}")
            continue
        actual_hash = sha256(dest)
        if old_hash and actual_hash != old_hash:
            mismatches.append(f"locally modified: {dest.relative_to(project)}")
        elif actual_hash != expected_hash or old_hash != expected_hash:
            upgrades.append(key)
    if mismatches:
        print(f"FAIL check: {project.name} has locally modified kit files")
        for m in mismatches:
            print(f"  - {m}")
        return 1
    if upgrades:
        print(f"FAIL check: {project.name} kit is intact, but {len(upgrades)} file(s) require --upgrade.")
        for u in upgrades:
            print(f"  - {u}")
        return 2
    print(f"OK check: {project.name} kit matches skill source exactly")
    return 0


def upgrade(project: Path) -> int:
    manifest_path = project / MANIFEST_NAME
    if not manifest_path.is_file():
        print(f"No manifest in {project.name}. Running fresh install.")
        return do_copy(project, "install")
    saved = json.loads(manifest_path.read_text())
    locally_modified = []
    upgraded = 0
    manifest = build_manifest()
    for key, dest_rel, content in kit_payloads():
        dest = project / dest_rel
        old_hash = saved.get("files", {}).get(key, "")
        actual_hash = sha256(dest) if dest.is_file() else ""
        expected_hash = sha256_bytes(content)
        if dest.is_file() and actual_hash != expected_hash and (not old_hash or actual_hash != old_hash):
            locally_modified.append(key)
            manifest["files"][key] = old_hash
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        if actual_hash != expected_hash:
            dest.write_bytes(content)
            upgraded += 1
    if locally_modified:
        print(f"WARN: {len(locally_modified)} file(s) locally modified, skipped:")
        for f in locally_modified:
            print(f"  - {f}")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if upgraded:
        print(f"OK upgrade: {upgraded} file(s) updated in {project.name}")
    else:
        print(f"OK upgrade: nothing to update in {project.name}")
    return 0 if not locally_modified else 2


def build_source_css() -> int:
    css_path = KIT_DIR / LESSON_CSS_KEY
    css_path.write_text(build_lesson_css(css_path.parent), encoding="utf-8")
    print(f"OK build-css: {css_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--install", action="store_true")
    group.add_argument("--check", action="store_true")
    group.add_argument("--upgrade", action="store_true")
    group.add_argument("--build-css", action="store_true")
    args = parser.parse_args()

    if args.build_css:
        return build_source_css()
    if not args.project:
        parser.error("--project is required unless --build-css is used")
    project = args.project.resolve()
    if not project.is_dir():
        print(f"Project not found: {project}", file=sys.stderr)
        return 1

    if args.install:
        return install(project)
    if args.check:
        return check(project)
    if args.upgrade:
        return upgrade(project)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
