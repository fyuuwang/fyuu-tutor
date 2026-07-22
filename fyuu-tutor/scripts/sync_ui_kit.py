#!/usr/bin/env python3
"""Install, check, or upgrade the Fyuu Tutor UI kit in a learning project."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
KIT_DIR = SKILL_DIR / "assets" / "ui-kit"

# Files to sync: (source_relative_to_kit, dest_relative_to_project)
KIT_FILES = [
    ("assets/lesson.css", "outputs/assets/lesson.css"),
    ("assets/tokens.css", "outputs/assets/tokens.css"),
    ("assets/foundation.css", "outputs/assets/foundation.css"),
    ("assets/components.css", "outputs/assets/components.css"),
    ("assets/lesson.js", "outputs/assets/lesson.js"),
    ("templates/lesson.html", "outputs/templates/lesson.html"),
    ("templates/practice.html", "outputs/templates/practice.html"),
    ("templates/reference.html", "outputs/templates/reference.html"),
    ("templates/components.html", "outputs/templates/components.html"),
    ("ui-spec.json", "outputs/ui/ui-spec.json"),
]

MANIFEST_NAME = "outputs/ui/kit-manifest.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest() -> dict:
    """Build manifest from current skill kit files."""
    entries = {}
    for src_rel, _ in KIT_FILES:
        src = KIT_DIR / src_rel
        entries[src_rel] = sha256(src) if src.is_file() else ""
    return {"kit_version": "2", "files": entries}


def install(project: Path) -> int:
    dest_manifest = project / MANIFEST_NAME
    if dest_manifest.is_file():
        print(f"UI kit already installed in {project.name}. Use --upgrade to update.")
        return 1
    return do_copy(project, "install")


def do_copy(project: Path, action: str) -> int:
    copied = 0
    for src_rel, dest_rel in KIT_FILES:
        src = KIT_DIR / src_rel
        dest = project / dest_rel
        if not src.is_file():
            print(f"  WARN: source missing: {src_rel}", file=sys.stderr)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied += 1
    manifest = build_manifest()
    (project / MANIFEST_NAME).parent.mkdir(parents=True, exist_ok=True)
    json.dump(manifest, open(project / MANIFEST_NAME, "w"), indent=2)
    print(f"OK {action}: {copied} files synced to {project.name}")
    return 0


def check(project: Path) -> int:
    manifest_path = project / MANIFEST_NAME
    if not manifest_path.is_file():
        print(f"FAIL: no kit-manifest.json in {project.name}. Run --install first.")
        return 1
    saved = json.loads(manifest_path.read_text())
    current = build_manifest()
    mismatches = []
    for src_rel, _ in KIT_FILES:
        old_hash = saved.get("files", {}).get(src_rel, "")
        dest = project / KIT_DEST(src_rel)
        if not dest.is_file():
            mismatches.append(f"missing: {dest.relative_to(project)}")
            continue
        new_hash = sha256(dest)
        skill_hash = sha256(KIT_DIR / src_rel) if (KIT_DIR / src_rel).is_file() else ""
        if new_hash != old_hash:
            mismatches.append(f"locally modified: {dest.relative_to(project)}")
        if skill_hash and new_hash != skill_hash and old_hash == skill_hash:
            # File was locally modified, don't auto-flag as needing upgrade
            pass
    # Check if skill has newer versions
    upgrades = []
    for src_rel, _ in KIT_FILES:
        src = KIT_DIR / src_rel
        dest = project / KIT_DEST(src_rel)
        if not src.is_file() or not dest.is_file():
            continue
        if sha256(src) != sha256(dest):
            old_hash = saved.get("files", {}).get(src_rel, "")
            if old_hash == sha256(dest):
                upgrades.append(src_rel)
    if mismatches:
        print(f"FAIL check: {project.name} has locally modified kit files")
        for m in mismatches:
            print(f"  - {m}")
        return 1
    if upgrades:
        print(f"OK check: {project.name} kit intact, but {len(upgrades)} file(s) have skill updates available. Use --upgrade.")
        for u in upgrades:
            print(f"  - {u}")
        return 0
    print(f"OK check: {project.name} kit matches skill source exactly")
    return 0


def KIT_DEST(src_rel: str) -> str:
    for s, d in KIT_FILES:
        if s == src_rel:
            return d
    return src_rel


def upgrade(project: Path) -> int:
    manifest_path = project / MANIFEST_NAME
    if not manifest_path.is_file():
        print(f"No manifest in {project.name}. Running fresh install.")
        return do_copy(project, "install")
    saved = json.loads(manifest_path.read_text())
    locally_modified = []
    upgraded = 0
    for src_rel, dest_rel in KIT_FILES:
        src = KIT_DIR / src_rel
        dest = project / dest_rel
        if not src.is_file():
            continue
        old_hash = saved.get("files", {}).get(src_rel, "")
        if dest.is_file() and sha256(dest) != old_hash and old_hash:
            locally_modified.append(dest_rel)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        upgraded += 1
    if locally_modified:
        print(f"WARN: {len(locally_modified)} file(s) locally modified, skipped:")
        for f in locally_modified:
            print(f"  - {f}")
    manifest = build_manifest()
    json.dump(manifest, open(project / MANIFEST_NAME, "w"), indent=2)
    if upgraded:
        print(f"OK upgrade: {upgraded} file(s) updated in {project.name}")
    else:
        print(f"OK upgrade: nothing to update in {project.name}")
    return 0 if not locally_modified else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--install", action="store_true")
    group.add_argument("--check", action="store_true")
    group.add_argument("--upgrade", action="store_true")
    args = parser.parse_args()

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
