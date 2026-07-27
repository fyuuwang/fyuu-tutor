#!/usr/bin/env python3
"""Wraps portal build and deployment into a single verifiable command.

Reads a private <workspace>/portal.toml, validates every project, builds
the portal, runs privacy and link checks, and optionally pushes to GitHub
Pages via deploy_portal.sh.

Usage:
    python3 publish_portal.py --workspace <workspace> --config <workspace>/portal.toml --build-only
    python3 publish_portal.py --workspace <workspace> --config <workspace>/portal.toml --publish
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import stat
import subprocess as sp
import sys
import tempfile
import tomllib
from pathlib import Path

sys.dont_write_bytecode = True


def read_config(config_path: Path) -> dict:
    """Load portal.toml, reject missing/invalid fields."""
    if not config_path.is_file():
        print(f"ERROR: config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)
    try:
        cfg = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: cannot parse {config_path}: {exc}", file=sys.stderr)
        sys.exit(1)
    portal = cfg.get("portal", {})
    if not isinstance(portal, dict):
        print("ERROR: [portal] section missing", file=sys.stderr)
        sys.exit(1)
    projects = portal.get("projects", [])
    if not isinstance(projects, list) or len(projects) == 0:
        print("ERROR: portal.projects must be a non-empty list", file=sys.stderr)
        sys.exit(1)
    if len(projects) != len(set(projects)):
        print("ERROR: portal.projects contains duplicates", file=sys.stderr)
        sys.exit(1)
    repo = portal.get("repo", "")
    marker_file = portal.get("marker_file")
    if not isinstance(marker_file, str) or not marker_file.strip():
        print("ERROR: portal.marker_file must be a non-empty string", file=sys.stderr)
        sys.exit(1)
    return {
        "projects": projects,
        "repo": repo,
        "marker_file": marker_file,
    }


def _run(cmd: list[str], label: str) -> tuple[int, str]:
    r = sp.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"ERROR: {label} failed:", file=sys.stderr)
        if r.stdout.strip():
            print(r.stdout, file=sys.stderr)
        if r.stderr.strip():
            print(r.stderr, file=sys.stderr)
    return r.returncode, (r.stdout + r.stderr)


def _project_root(workspace: Path, pid: str) -> Path:
    from project_config import load_project
    projects_root = workspace / "projects"
    for d in sorted(projects_root.iterdir()):
        toml = d / "project.toml"
        if not toml.is_file():
            continue
        _, config, _ = load_project(d)
        if config.get("project_id") == pid:
            return d
    return None


def _status_value(status_path: Path, field: str) -> str:
    from project_config import status_value
    return status_value(status_path.read_text(encoding="utf-8"), field, missing="")


def _read_regular_file(path: Path) -> tuple[os.stat_result, bytes]:
    """Read one regular file through one non-following descriptor."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        print(f"ERROR: cannot open marker file safely: {path} ({exc})", file=sys.stderr)
        sys.exit(1)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            os.close(fd)
            print(f"ERROR: marker file is not a regular file: {path}", file=sys.stderr)
            sys.exit(1)
        with os.fdopen(fd, "rb") as f:
            return info, f.read()
    except OSError as exc:
        try:
            os.close(fd)
        except OSError:
            pass
        print(f"ERROR: cannot read marker file: {path} ({exc})", file=sys.stderr)
        sys.exit(1)


def _validate_marker_file(workspace: Path, marker_file_cfg: str) -> tuple[Path, list[str]]:
    """Validate the marker file fail-closed; return (resolved_path, markers).

    `workspace` must already be resolved to a real directory.  Symlink checks
    run on the configured path BEFORE resolve() dereferences it: resolve()
    follows symlinks, so checking `resolved.is_symlink()` afterwards is always
    False and lets a marker such as `marker.txt -> real.txt` through.
    """
    cfg_parts = Path(marker_file_cfg).parts
    if (marker_file_cfg.startswith("/") or Path(marker_file_cfg).is_absolute()
            or ".." in cfg_parts):
        print(f"ERROR: marker_file must be a simple relative path inside the "
              f"workspace: {marker_file_cfg!r}", file=sys.stderr)
        sys.exit(1)

    raw = workspace / marker_file_cfg

    # Walk every component of the configured path before resolving.  A symlink
    # at any level (the file itself or a parent directory) must fail-closed.
    check = raw
    while check != workspace:
        if check.is_symlink():
            print(f"ERROR: marker path must not contain a symlink: {check}",
                  file=sys.stderr)
            sys.exit(1)
        parent = check.parent
        if parent == check:  # reached filesystem root without hitting workspace
            break
        check = parent

    try:
        resolved = raw.resolve(strict=True)
    except (FileNotFoundError, OSError, RuntimeError) as exc:
        print(f"ERROR: marker file not found: {raw} ({exc})", file=sys.stderr)
        sys.exit(1)

    # Must resolve inside the workspace and remain a real file.
    try:
        resolved.relative_to(workspace)
    except ValueError:
        print(f"ERROR: marker file outside workspace: {resolved}", file=sys.stderr)
        sys.exit(1)
    if resolved.is_symlink():
        print(f"ERROR: marker file must not be a symlink: {resolved}", file=sys.stderr)
        sys.exit(1)
    try:
        _, data = _read_regular_file(resolved)
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        print(f"ERROR: marker file is not valid UTF-8: {resolved}", file=sys.stderr)
        sys.exit(1)
    except OSError as exc:
        print(f"ERROR: cannot read marker file: {resolved} ({exc})", file=sys.stderr)
        sys.exit(1)

    # Strip before testing for comment so indented "# ..." lines are not
    # mistaken for markers, and a comment-only file is treated as empty.
    markers = [stripped for line in text.splitlines()
               if (stripped := line.strip()) and not stripped.startswith("#")]
    if not markers:
        print(f"ERROR: marker file has no non-comment markers: {resolved}",
              file=sys.stderr)
        sys.exit(1)

    return resolved, markers


def _marker_snapshot(markers: list[str]) -> tuple[Path, Path, int, bytes]:
    """Write validated markers once so downstream readers cannot race the source."""
    directory = Path(tempfile.mkdtemp(prefix="portal-markers."))
    os.chmod(directory, 0o700)
    path = directory / "markers.txt"
    path.write_text("\n".join(markers) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)
    info, data = _read_regular_file(path)
    return directory, path, info.st_ino, hashlib.sha256(data).digest()


def _verify_marker_snapshot(path: Path, inode: int, digest: bytes) -> bool:
    """Fail closed if a same-user process has replaced the snapshot."""
    try:
        info, data = _read_regular_file(path)
    except SystemExit:
        return False
    return info.st_ino == inode and hashlib.sha256(data).digest() == digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--config", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--build-only", action="store_true")
    group.add_argument("--publish", action="store_true")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    config_path = Path(args.config).resolve()
    scripts_dir = Path(__file__).resolve().parent
    system_root = scripts_dir.parent.parent

    cfg = read_config(config_path)
    authorized = set(cfg["projects"])

    # Validate marker file BEFORE any project validation (fail-closed gate)
    _, markers = _validate_marker_file(workspace, cfg["marker_file"])
    markers_dir, markers_path, markers_inode, markers_digest = _marker_snapshot(markers)
    try:
        # Validate each project
        for pid in authorized:
            root = _project_root(workspace, pid)
            if root is None:
                print(f"ERROR: project_id not found: {pid}", file=sys.stderr)
                return 1
            state = _status_value(root / "STATUS.md", "State")
            if state != "idle":
                print(f"ERROR: project {pid} must be idle (found {state})", file=sys.stderr)
                return 1
            checks = [
                (["validate_project.py", "--project", str(root)], "project validation"),
                (["sync_ui_kit.py", "--project", str(root), "--check"], "UI Kit check"),
                (["validate_lesson_ui.py", "--project", str(root)], "UI page check"),
            ]
            for cmd_args, label in checks:
                rc, _ = _run([sys.executable, str(scripts_dir / cmd_args[0])] + cmd_args[1:], label)
                if rc != 0:
                    return 1

        # Build portal into staging (with the validated marker snapshot).
        portal_tmp = Path(tempfile.mkdtemp(prefix="portal-build."))
        build_args = [sys.executable, str(scripts_dir / "build_portal.py"),
                      "--workspace", str(workspace), "--out", str(portal_tmp), "--overwrite",
                      "--markers", str(markers_path)]
        for pid in authorized:
            build_args += ["--project", pid]
        if not _verify_marker_snapshot(markers_path, markers_inode, markers_digest):
            print("ERROR: marker snapshot changed before portal build", file=sys.stderr)
            return 1
        rc, out = _run(build_args, "portal build")
        if rc != 0:
            shutil.rmtree(portal_tmp, ignore_errors=True)
            return 1

        # Post-build privacy and link checks (second gate)
        from build_portal import scan_content
        errors = scan_content(portal_tmp, markers)
        if errors:
            print("ERROR: privacy scan failed:", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)
            shutil.rmtree(portal_tmp, ignore_errors=True)
            return 1

        rc, _ = _run([sys.executable, str(scripts_dir / "check_links.py"), "--root", str(portal_tmp)],
                     "portal link check")
        if rc != 0:
            shutil.rmtree(portal_tmp, ignore_errors=True)
            return 1

        if args.build_only:
            pages = sum(1 for _ in portal_tmp.rglob("*.html"))
            print(f"OK build-only: {portal_tmp} ({pages} pages, {len(authorized)} projects)")
            return 0

        # --publish: check system repo state
        repo = (workspace / cfg["repo"]).resolve()
        if not (repo / ".git").exists():
            print(f"ERROR: --repo is not a git repository: {repo}", file=sys.stderr)
            shutil.rmtree(portal_tmp, ignore_errors=True)
            return 1
        branch = sp.run(["git", "-C", str(repo), "branch", "--show-current"],
                        capture_output=True, text=True).stdout.strip()
        if branch != "main":
            print(f"ERROR: --publish requires the main branch (found {branch})", file=sys.stderr)
            shutil.rmtree(portal_tmp, ignore_errors=True)
            return 1
        dirty = sp.run(["git", "-C", str(repo), "status", "--porcelain"],
                       capture_output=True, text=True).stdout.strip()
        if dirty:
            print(f"ERROR: --publish requires a clean worktree", file=sys.stderr)
            shutil.rmtree(portal_tmp, ignore_errors=True)
            return 1

        # Deploy via deploy_portal.sh (with the same snapshot)
        deploy_args = ["bash", str(scripts_dir / "deploy_portal.sh"),
                       "--workspace", str(workspace), "--repo", str(repo),
                       "--markers", str(markers_path)]
        for pid in authorized:
            deploy_args += ["--project", pid]
        deploy_args += ["--publish"]
        if not _verify_marker_snapshot(markers_path, markers_inode, markers_digest):
            print("ERROR: marker snapshot changed before portal deploy", file=sys.stderr)
            return 1
        rc, out = _run(deploy_args, "portal deploy")
        shutil.rmtree(portal_tmp, ignore_errors=True)
        if rc != 0:
            return 1

        # Report deployed commit
        sha = sp.run(["git", "-C", str(repo), "rev-parse", "gh-pages"],
                     capture_output=True, text=True).stdout.strip()
        print(f"OK published: gh-pages commit {sha}")
        return 0
    finally:
        shutil.rmtree(markers_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
