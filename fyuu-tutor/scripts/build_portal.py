#!/usr/bin/env python3
"""Build a public learning portal from explicitly selected projects.

Only copies whitelisted lesson/reference HTML and CSS/JS assets.
Never copies private metadata, project index, or unapproved file types.
Requires explicit --project selection; never publishes all projects by default.

Usage:
    python3 build_portal.py --workspace workspace --out portal \
        --project example-capability --project example-certification
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
from html import escape
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_config import load_project, status_value

# File whitelist: only these subdirs and extensions are copied from outputs/
ALLOWED_HTML_SUBDIRS = ("lessons", "reference")
ALLOWED_ASSET_EXTS = {".css", ".js"}

# Absolute-path patterns that must never appear in published content
# Built via concatenation to avoid self-triggering the privacy auditor
_U = "/" + "Users/"
_H = "/" + "home/"
_P = "/" + "private/"
ABSOLUTE_PATH_RES = [
    re.compile(_U + r"[^/\s]+/"),
    re.compile(_H + r"[^/\s]+/"),
    re.compile(_P + r"[^/\s]+/"),
    re.compile(r"[A-Za-z]:\\" + "Users" + r"\\"),
]

PORTAL_CSS = """
:root{--bg:#f5f1e8;--card:#fffdf8;--ink:#27231f;--muted:#746c62;--accent:#aa4a2a;--line:#ded5c8;--blue:#3b6ea5}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,-apple-system,sans-serif}
main{max-width:920px;margin:auto;padding:42px 20px 80px}
h1{margin:0 0 6px;font-size:clamp(28px,6vw,48px)}h2{margin:36px 0 12px}
.muted{color:var(--muted)}.intro{color:var(--muted);margin:0 0 28px}
.proj{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:24px;margin-bottom:20px}
.proj-head{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.proj-head h2{margin:0;font-size:22px}
.badge{display:inline-block;padding:2px 10px;border-radius:20px;font-size:12px;font-weight:600;background:var(--accent);color:#fff}
.badge.cert{background:var(--blue)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin-top:12px}
.card{display:block;background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:12px 14px;color:inherit;text-decoration:none;transition:border-color .15s,transform .15s}
.card:hover{border-color:var(--accent);transform:translateY(-1px)}
.card strong{display:block;font-size:15px;line-height:1.4}
.card .lbl{display:inline-block;margin-top:6px;font-size:11px;color:var(--accent)}
footer{margin-top:48px;padding-top:20px;border-top:1px solid var(--line);color:var(--muted);font-size:13px}
@media(max-width:520px){main{padding:28px 16px 60px}.proj{padding:16px}}
"""


def safe_slug(name: str) -> str:
    """URL-safe slug from a project display name."""
    slug = re.sub(r"[^\w\s-]", "", name, flags=re.UNICODE).strip().lower()
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug or "project"


def page_title(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
        m = re.search(r"<title>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()
    except Exception:
        pass
    return path.stem



def is_symlink_safe(path: Path) -> bool:
    """Return False if path or any parent is a symlink."""
    if path.is_symlink():
        return False
    for parent in path.parents:
        if parent.is_symlink():
            return False
    return True


def check_output_dir(out_dir: Path, workspace: Path) -> None:
    """Refuse dangerous output directories — bidirectional protection.

    Output must not BE a protected dir, be INSIDE one, or CONTAIN one.
    Without the contain-check, --overwrite could delete workspace or git root.
    """
    out_r = out_dir.resolve()
    git_root = Path(__file__).resolve().parent.parent.parent

    # Protected paths that must never be deleted or overwritten
    protected = [workspace.resolve(), (workspace / "projects").resolve(),
                 git_root.resolve()]
    projects_root = workspace / "projects"
    if projects_root.is_dir():
        for p in projects_root.iterdir():
            protected.append(p.resolve())

    for prot in protected:
        try:
            prot_r = prot.resolve()
        except Exception:
            continue
        # Reject: output IS protected, output is INSIDE protected,
        # or output CONTAINS protected (would delete it on --overwrite)
        if out_r == prot_r or prot_r in out_r.parents or out_r in prot_r.parents:
            print(f"ERROR: refusing output that would affect protected path: {prot_r}", file=sys.stderr)
            sys.exit(1)

    # Also reject root and home exactly (equality only — temp dirs are under these)
    for eq in (Path("/"), Path.home()):
        if out_r == eq.resolve():
            print(f"ERROR: refusing dangerous output path: {eq.resolve()}", file=sys.stderr)
            sys.exit(1)

    # Reject current working directory
    cwd = Path.cwd().resolve()
    if out_r == cwd or out_r in cwd.parents or cwd in out_r.parents:
        print("ERROR: refusing to overwrite current directory tree", file=sys.stderr)
        sys.exit(1)


def copy_whitelisted(project_root: Path, dest: Path) -> list[tuple[str, str]]:
    """Copy only whitelisted files from outputs/. Returns [(rel_path, title)] for HTML pages."""
    outputs = project_root / "outputs"
    if not outputs.is_dir():
        print(f"WARNING: no outputs/ in {project_root.name}", file=sys.stderr)
        return []

    pages: list[tuple[str, str]] = []

    for sub in ALLOWED_HTML_SUBDIRS:
        subdir = outputs / sub
        if not subdir.is_dir():
            continue
        for html in sorted(subdir.rglob("*.html")):
            if not is_symlink_safe(html):
                raise RuntimeError(f"symlink detected: {html}")
            rel = html.relative_to(outputs)
            out_file = dest / rel
            out_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(html, out_file)
            pages.append((str(rel).replace("\\", "/"), page_title(html)))

    assets = outputs / "assets"
    if assets.is_dir():
        for f in sorted(assets.rglob("*")):
            if f.is_dir() or f.suffix not in ALLOWED_ASSET_EXTS:
                continue
            if not is_symlink_safe(f):
                raise RuntimeError(f"symlink detected: {f}")
            rel = f.relative_to(outputs)
            out_file = dest / rel
            out_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, out_file)

    return pages


def scan_content(out_dir: Path, markers: list[str]) -> list[str]:
    """Scan all published text files for absolute paths, markers, and file:// links."""
    errors: list[str] = []
    for path in sorted(out_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(out_dir)
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as e:
            errors.append(f"unreadable file (not checked, refusing to publish): {rel}: {e}")
            continue
        for pat in ABSOLUTE_PATH_RES:
            if pat.search(text):
                errors.append(f"absolute path in {rel}")
                break
        if "file://" in text.lower():
            errors.append(f"file:// reference in {rel}")
        for marker in markers:
            if marker and marker in text:
                errors.append(f"private marker {marker!r} in {rel}")
                break
    return errors


def cards_html(items: list[tuple[str, str]], label: str) -> str:
    if not items:
        return ""
    rows = "".join(
        f'<a class="card" href="{escape(h)}"><strong>{escape(t)}</strong>'
        f'<span class="lbl">{escape(label)}</span></a>'
        for h, t in sorted(items, key=lambda item: item[0])
    )
    return f'<div class="grid">{rows}</div>'


def project_index_html(display_name: str, pipeline: str, slug: str,
                       pages: list[tuple[str, str]]) -> str:
    """Generate a public per-project index page (no STATUS data)."""
    pipeline_label = {"capability": "能力培养", "certification": "认证备考",
                      "language": "语言学习"}.get(pipeline, pipeline)
    lessons = [(h, t) for h, t in pages if h.startswith("lessons/")]
    references = [(h, t) for h, t in pages if h.startswith("reference/")]

    back = "../index.html"
    return f"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(display_name)} · 课程入口</title>
<style>{PORTAL_CSS}</style></head>
<body><main>
<p><a href="{back}">← 返回学习门户</a></p>
<h1>{escape(display_name)}</h1><p class="muted">{escape(pipeline_label)}</p>
<h2>课程</h2>{cards_html(lessons, "课程")}
<h2>参考资料</h2>{cards_html(references, "速查")}
<footer>由 Fyuu Tutor Skill 自动生成 · 仅含课件内容</footer>
</main></body></html>
"""


def portal_html(projects: list[tuple[str, str, str, list[tuple[str, str]]]]) -> str:
    """Generate the portal landing page."""
    project_cards = []
    for display_name, pipeline, slug, pages in projects:
        pipeline_label = {"capability": "能力培养", "certification": "认证备考",
                          "language": "语言学习"}.get(pipeline, pipeline)
        badge_cls = "badge cert" if pipeline == "certification" else "badge"
        lessons = [(f"{slug}/{h}", t) for h, t in pages if h.startswith("lessons/")]
        refs = [(f"{slug}/{h}", t) for h, t in pages if h.startswith("reference/")]

        index_link = f"{slug}/index.html"
        project_cards.append(f"""
<section class="proj">
<div class="proj-head"><h2>{escape(display_name)}</h2><span class="{badge_cls}">{escape(pipeline_label)}</span></div>
<a class="card" href="{escape(index_link)}" style="margin-top:10px"><strong>进入课程入口</strong></a>
{cards_html(lessons, "课程")}{cards_html(refs, "速查")}
</section>""")

    body = "".join(project_cards)
    return f"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fyuu Tutor · 学习门户</title>
<style>{PORTAL_CSS}</style></head>
<body><main>
<h1>Fyuu Tutor</h1>
<p class="intro">选择一个学习项目，开始今天的课程。所有课件离线可用，手机也能看。</p>
{body}
<footer>由 Fyuu Tutor Skill 自动生成 · 仅含课件内容，不含私人数据</footer>
</main></body></html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--project", action="append", required=True,
                        help="project_id to publish (repeatable)")
    parser.add_argument("--overwrite", action="store_true",
                        help="allow overwriting existing output directory")
    parser.add_argument("--markers", help="file with private marker strings (one per line)")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    projects_root = workspace / "projects"
    out_dir = Path(args.out).resolve()

    if not projects_root.is_dir():
        print(f"ERROR: projects dir not found: {projects_root}", file=sys.stderr)
        return 1

    # Output directory protection
    check_output_dir(out_dir, workspace)

    if out_dir.exists() and not args.overwrite:
        print(f"ERROR: output exists, use --overwrite: {out_dir}", file=sys.stderr)
        return 1

    # Load markers
    markers: list[str] = []
    if args.markers:
        markers = [line.strip() for line in Path(args.markers).read_text(encoding="utf-8").splitlines()
                   if line.strip() and not line.startswith("#")]

    # Build to a uniquely-named staging directory in out_dir.parent (same
    # filesystem) so the final swap is an atomic rename. Never assume a fixed
    # name -- the user may have an unrelated directory with that name.
    staging = Path(tempfile.mkdtemp(dir=str(out_dir.parent), prefix=out_dir.name + ".staging."))
    staging.mkdir(parents=True, exist_ok=True)
    try:
        scripts = Path(__file__).resolve().parent
        portal_projects, ok = _build_to_dir(staging, workspace, projects_root, args.project, markers, scripts)
        if not ok:
            shutil.rmtree(staging, ignore_errors=True)
            return 1
        # Scan passed - atomic swap via rename (same filesystem, no partial copy):
        # 1. rename old output -> backup
        # 2. rename staging -> output (atomic on same filesystem)
        # 3. on failure: remove any half-written output, rename backup back
        backup = None
        if out_dir.exists():
            backup = Path(tempfile.mkdtemp(dir=str(out_dir.parent), prefix=out_dir.name + ".backup."))
            shutil.rmtree(backup)
            out_dir.rename(backup)
        try:
            staging.rename(out_dir)
            if backup:
                shutil.rmtree(backup, ignore_errors=True)
        except Exception as exc:
            # Rename failed: clean up half-written output (if any), restore backup,
            # then report failure (do not re-raise -- main() returns 1).
            if out_dir.exists():
                shutil.rmtree(out_dir, ignore_errors=True)
            if backup and backup.exists():
                backup.rename(out_dir)
            shutil.rmtree(backup, ignore_errors=True)
            print(f"ERROR: failed to publish portal, old output restored: {exc}", file=sys.stderr)
            return 1
    except Exception as exc:
        shutil.rmtree(staging, ignore_errors=True)
        print(f"ERROR: portal build failed: {exc}", file=sys.stderr)
        return 1

    total = sum(len(p[3]) for p in portal_projects)
    print(f"\nOK portal: {out_dir} ({total} pages, {len(portal_projects)} projects)")
    return 0


def _validate_project_or_fail(project_root: Path, pid: str, scripts_dir: Path) -> bool:
    import subprocess as sp
    checks = (
        ("project validation", [sys.executable, str(scripts_dir / "validate_project.py"), "--project", str(project_root)]),
        ("UI Kit check", [sys.executable, str(scripts_dir / "sync_ui_kit.py"), "--project", str(project_root), "--check"]),
        ("UI page check", [sys.executable, str(scripts_dir / "validate_lesson_ui.py"), "--project", str(project_root)]),
    )
    for index, (label, command) in enumerate(checks):
        r = sp.run(command, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"ERROR: {label} failed for {pid}:", file=sys.stderr)
            if r.stdout.strip(): print(r.stdout, file=sys.stderr)
            if r.stderr.strip(): print(r.stderr, file=sys.stderr)
            return False
        if index == 0:
            manifest = project_root / "outputs" / "ui" / "kit-manifest.json"
            if not manifest.is_file():
                print(f"ERROR: missing kit-manifest for {pid}: {manifest}", file=sys.stderr)
                return False
    return True
def _build_to_dir(staging: Path, workspace: Path, projects_root: Path,
                  project_ids: list[str], markers: list[str],
                  scripts_dir: Path) -> tuple[list, bool]:
    """Build portal into staging dir, scan, return (projects, success)."""
    portal_projects: list[tuple[str, str, str, list[tuple[str, str]]]] = []
    seen_slugs: dict[str, str] = {}

    for pid in project_ids:
        matches = []
        for project_root in sorted(projects_root.iterdir()):
            toml_path = project_root / "project.toml"
            if not toml_path.is_file():
                continue
            _, config, _ = load_project(project_root)
            if config.get("project_id") == pid:
                matches.append((project_root, config))
        if len(matches) > 1:
            print(f"ERROR: project_id {pid!r} is ambiguous ({len(matches)} dirs): "
                  + ", ".join(m[0].name for m in matches), file=sys.stderr)
            return [], False
        if not matches:
            print(f"ERROR: project_id not found: {pid}", file=sys.stderr)
            return [], False

        project_root, config = matches[0]
        display_name = config.get("display_name", project_root.name)
        pipeline = config.get("pipeline", "capability")
        slug = safe_slug(display_name)

        # Validate project and UI Kit before copying any content
        if not _validate_project_or_fail(project_root, pid, scripts_dir):
            return [], False
        state = status_value((project_root / "STATUS.md").read_text(encoding="utf-8"), "State")
        if state != "idle":
            print(f"ERROR: project {pid} must be idle before portal build (found {state})", file=sys.stderr)
            return [], False

        if slug in seen_slugs:
            print(f"ERROR: slug collision: {slug} (from {pid} and {seen_slugs[slug]})", file=sys.stderr)
            return [], False
        seen_slugs[slug] = pid

        proj_dest = staging / slug
        copied = copy_whitelisted(project_root, proj_dest)
        (proj_dest / "index.html").write_text(
            project_index_html(display_name, pipeline, slug, copied), encoding="utf-8")

        portal_projects.append((display_name, pipeline, slug, copied))
        print(f"  {display_name} ({pipeline}): {len(copied)} pages -> {slug}/")

    # Generate every public file before the final security scan.
    (staging / "index.html").write_text(portal_html(portal_projects), encoding="utf-8")

    # Content security scan on staging (before publishing)
    errors = scan_content(staging, markers)
    if errors:
        print("ERROR: content security check failed:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return [], False

    import subprocess as sp
    links = sp.run([sys.executable, str(scripts_dir / "check_links.py"), "--root", str(staging)],
                   capture_output=True, text=True)
    if links.returncode != 0:
        print("ERROR: staging link check failed:", file=sys.stderr)
        if links.stdout.strip(): print(links.stdout, file=sys.stderr)
        if links.stderr.strip(): print(links.stderr, file=sys.stderr)
        return [], False
    return portal_projects, True


if __name__ == "__main__":
    raise SystemExit(main())
