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

# Fixed order of public projects on the root portal: PMP, Cantonese, AI.
# project_id -> sort key. Projects not listed here sort after, by display name.
PROJECT_ORDER = {
    "pmp-certification": 0,
    "business-cantonese": 1,
    "ai-systems-designer": 2,
}

# Stable hash fragment per project_id, for #hash tab routing on the root portal.
# Falls back to the project slug when an id is not listed here.
PROJECT_HASH = {
    "pmp-certification": "pmp",
    "business-cantonese": "cantonese",
    "ai-systems-designer": "ai",
}

PIPELINE_LABELS = {
    "capability": "能力培养",
    "certification": "认证备考",
    "language": "语言学习",
}

PIPELINE_BLURBS = {
    "capability": "围绕一个能力，按台阶练到能独立交付。",
    "certification": "以官方考纲为权威，构建可验证的备考路径。",
    "language": "以场景和输出为驱动，把一门语言用到能用。",
}

# Hash fragments for the per-project catalog tabs (课程 / 复习 / 资料).
TAB_HASH = ("lessons", "review", "reference")
TAB_LABELS = {"lessons": "课程", "review": "复习", "reference": "资料"}

PORTAL_CSS = """\
:root{--bg:#f5f1e8;--card:#fffdf8;--ink:#27231f;--muted:#746c62;--accent:#aa4a2a;--line:#ded5c8;--blue:#3b6ea5}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,-apple-system,sans-serif}
main{max-width:920px;margin:auto;padding:42px 20px 80px}
h1{margin:0 0 6px;font-size:clamp(28px,6vw,48px)}
.muted{color:var(--muted)}.intro{color:var(--muted);margin:0 0 28px}
.tabs{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:0 0 24px;border-bottom:1px solid var(--line)}
.tab{display:flex;align-items:center;justify-content:center;min-height:48px;padding:10px 12px;border:1px solid var(--line);border-bottom:none;border-radius:10px 10px 0 0;background:var(--bg);color:var(--muted);text-decoration:none;font-weight:600;font-size:15px;text-align:center}
.tab[aria-selected="true"]{background:var(--card);color:var(--ink);border-color:var(--accent)}
.tab .count{margin-left:6px;font-size:12px;font-weight:600;opacity:.8}
.panel{display:none}.panel[data-active="true"]{display:block}
.proj-head{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:4px}
.proj-head h2{margin:0;font-size:22px}
.badge{display:inline-block;padding:2px 10px;border-radius:20px;font-size:12px;font-weight:600;background:var(--accent);color:#fff}
.badge.cert{background:var(--blue)}
.blurb{color:var(--muted);margin:0 0 20px}
.entries{list-style:none;margin:0;padding:0}
.entry{display:flex;align-items:center;gap:10px;min-height:48px;padding:12px 14px;border:1px solid var(--line);border-radius:10px;margin-bottom:10px;background:var(--card);color:inherit;text-decoration:none;transition:border-color .15s}
.entry:hover{border-color:var(--accent)}
.entry .num{flex:0 0 auto;min-width:30px;font-variant-numeric:tabular-nums;font-weight:700;color:var(--accent)}
.entry .tag{flex:0 0 auto;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;background:var(--bg);color:var(--muted);border:1px solid var(--line)}
.entry .title{flex:1 1 auto;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;line-height:1.4}
.empty{padding:18px;border:1px dashed var(--line);border-radius:10px;color:var(--muted);text-align:center}
.btn-back{display:inline-flex;align-items:center;gap:6px;margin-bottom:20px;padding:8px 14px;min-height:40px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink);text-decoration:none;font-weight:600}
.btn-back:hover{border-color:var(--accent)}
footer{margin-top:48px;padding-top:20px;border-top:1px solid var(--line);color:var(--muted);font-size:13px}
@media(max-width:520px){main{padding:28px 16px 60px}}
"""

# Hash + keyboard tab switching shared by the root portal and every project
# catalog. When JS is unavailable, every panel stays in source order and all
# links remain reachable (no hidden-by-default content).
PORTAL_JS = """\
(function () {
  function groups(scope) {
    return Array.prototype.slice.call(
      scope.querySelectorAll('[role="tablist"]'));
  }
  function tabsOf(list) {
    return Array.prototype.slice.call(
      list.querySelectorAll('[role="tab"]'));
  }
  function panelsOf(scope, groupId) {
    return Array.prototype.slice.call(
      scope.querySelectorAll('[role="tabpanel"][data-group="' + groupId + '"]'));
  }
  function select(list, tab) {
    var scope = list.closest('[data-tabs-scope]') || document;
    var groupId = list.getAttribute('data-group') || '';
    tabsOf(list).forEach(function (t) {
      var on = t === tab;
      t.setAttribute('aria-selected', on ? 'true' : 'false');
      if (t.id) {
        var p = scope.querySelector('[role="tabpanel"][aria-labelledby="' + t.id + '"]');
        if (p) p.setAttribute('data-active', on ? 'true' : 'false');
      }
    });
    panelsOf(scope, groupId).forEach(function (p) {
      p.setAttribute('data-active', 'false');
    });
    if (tab.id) {
      var panel = scope.querySelector('[role="tabpanel"][aria-labelledby="' + tab.id + '"]');
      if (panel) panel.setAttribute('data-active', 'true');
    }
  }
  function fromHash(scope) {
    var hash = (location.hash || '').replace(/^#/, '');
    if (!hash) return null;
    var tab = scope.querySelector('[role="tab"][data-hash="' + hash + '"]');
    return tab || null;
  }
  function activate(scope) {
    groups(scope).forEach(function (list) {
      var first = tabsOf(list)[0];
      var target = fromHash(scope) || first;
      if (target) select(list, target);
    });
  }
  function initScope(scope) {
    groups(scope).forEach(function (list) {
      tabsOf(list).forEach(function (tab) {
        tab.addEventListener('click', function (e) {
          e.preventDefault();
          var h = tab.getAttribute('data-hash');
          if (h) { location.hash = h; }
          select(list, tab);
        });
      });
    });
    activate(scope);
  }
  document.addEventListener('DOMContentLoaded', function () {
    initScope(document);
  });
  window.addEventListener('hashchange', function () {
    activate(document);
  });
  document.addEventListener('keydown', function (e) {
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    var active = document.activeElement;
    if (!active || active.getAttribute('role') !== 'tab') return;
    var list = active.closest('[role="tablist"]');
    if (!list) return;
    var tabs = tabsOf(list);
    var i = tabs.indexOf(active);
    if (i < 0) return;
    var n = e.key === 'ArrowRight' ? (i + 1) % tabs.length : (i - 1 + tabs.length) % tabs.length;
    var target = tabs[n];
    var h = target.getAttribute('data-hash');
    if (h) { location.hash = h; }
    select(list, target);
    target.focus();
    e.preventDefault();
  });
})();
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
        # A deployment worktree has Git metadata at its root. It is not part
        # of the published tree and must not be mistaken for portal content.
        if rel.parts and rel.parts[0] == ".git":
            continue
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


def _leading_number(path: str) -> tuple[int, str, str]:
    """Sort key fragment: leading number, trailing letter, then filename.

    `0003b-evm-instinct-drill` -> (3, "b", filename). Unnumbered items sort
    last by filename (high sentinel keeps them after numbered entries).
    """
    name = path.rsplit("/", 1)[-1]
    m = re.match(r"^(\d+)([a-zA-Z]?)", name)
    if m:
        return (int(m.group(1)), m.group(2).lower(), name)
    return (10 ** 9, "", name)


def classify_page(href: str, title: str) -> str:
    """Bucket a copied page into one of: lessons / review / reference.

    Rules (v0.5.2 information architecture):
      - reference/** -> reference
      - lessons/* whose filename contains `review` or whose title contains 复习 -> review
      - remaining lessons/* -> lessons
    """
    if href.startswith("reference/"):
        return "reference"
    if href.startswith("lessons/"):
        name = href.rsplit("/", 1)[-1]
        if "review" in name.lower() or "复习" in title:
            return "review"
        return "lessons"
    return "reference"


def sort_pages(pages: list[tuple[str, str]], category: str) -> list[tuple[str, str]]:
    """Stable order within a catalog category.

    Lessons/review: leading number, then trailing letter, then filename.
    Reference: by path then title.
    """
    if category in ("lessons", "review"):
        return sorted(pages, key=lambda ht: _leading_number(ht[0]))
    return sorted(pages, key=lambda ht: (ht[0], ht[1]))


def _entry_html(href: str, title: str, index: int, tag: str) -> str:
    """A single compact, clickable catalog row (>=44px tap target)."""
    return (
        f'<a class="entry" href="{escape(href)}">'
        f'<span class="num">{escape(str(index))}</span>'
        f'<span class="tag">{escape(tag)}</span>'
        f'<span class="title">{escape(title)}</span>'
        f'</a>'
    )


def _entries_html(items: list[tuple[str, str]], tag: str) -> str:
    """Render a catalog category list, or an explicit non-empty empty-state."""
    if not items:
        return '<p class="empty">暂无内容</p>'
    rows = "".join(_entry_html(h, t, i, tag) for i, (h, t) in enumerate(items, 1))
    return f'<div class="entries">{rows}</div>'


def project_index_html(display_name: str, pipeline: str, slug: str,
                       project_hash: str,
                       pages: list[tuple[str, str]]) -> str:
    """Generate a public per-project catalog (课程 / 复习 / 资料), no STATUS data."""
    pipeline_label = PIPELINE_LABELS.get(pipeline, pipeline)
    buckets: dict[str, list[tuple[str, str]]] = {c: [] for c in TAB_HASH}
    for href, title in pages:
        buckets[classify_page(href, title)].append((href, title))
    for cat in TAB_HASH:
        buckets[cat] = sort_pages(buckets[cat], cat)

    tabs = []
    panels = []
    for i, cat in enumerate(TAB_HASH):
        tab_id = f"tab-{cat}"
        panel_id = f"panel-{cat}"
        selected = "true" if i == 0 else "false"
        active = "true" if i == 0 else "false"
        count = len(buckets[cat])
        tabs.append(
            f'<a class="tab" id="{tab_id}" role="tab" href="#{cat}" '
            f'data-hash="{cat}" aria-selected="{selected}" '
            f'aria-controls="{panel_id}">'
            f'<span>{TAB_LABELS[cat]}</span>'
            f'<span class="count">{count}</span></a>'
        )
        panels.append(
            f'<div class="panel" id="{panel_id}" role="tabpanel" '
            f'data-group="catalog" data-active="{active}" '
            f'aria-labelledby="{tab_id}">'
            f'{_entries_html(buckets[cat], TAB_LABELS[cat])}</div>'
        )

    tablist = (
        f'<div class="tabs" role="tablist" data-group="catalog" '
        f'aria-label="{escape(display_name)} 课程目录">'
        + "".join(tabs) + '</div>'
    )
    body = "".join(panels)
    badge_cls = "badge cert" if pipeline == "certification" else "badge"
    return (
        '<!doctype html>\n'
        '<html lang="zh-CN">\n'
        '<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f'<title>{escape(display_name)} · 课程目录</title>\n'
        '<link rel="stylesheet" href="../portal.css"></head>\n'
        '<body data-tabs-scope><main>\n'
        f'<a class="btn-back" href="../index.html" aria-label="返回学习门户">\n'
        '<span aria-hidden="true">←</span><span>返回学习门户</span></a>\n'
        f'<div class="proj-head"><h1>{escape(display_name)}</h1>\n'
        f'<span class="{badge_cls}">{escape(pipeline_label)}</span></div>\n'
        f'<p class="blurb">{escape(PIPELINE_BLURBS.get(pipeline, pipeline_label))}</p>\n'
        f'{tablist}\n'
        f'{body}\n'
        '<footer>由 Fyuu Tutor Skill 自动生成 · 仅含课件内容</footer>\n'
        '</main>\n'
        '<script src="../portal.js"></script>\n'
        '</body></html>\n'
    )


def portal_html(projects: list[tuple[str, str, str, str, str, list[tuple[str, str]]]]) -> str:
    """Root portal: a project switcher only (no lesson cards on the root page)."""
    ordered = sorted(projects, key=lambda p: (PROJECT_ORDER.get(p[0], 100), p[0]))
    tabs = []
    panels = []
    for i, (pid, pipeline, display_name, slug, project_hash, _pages) in enumerate(ordered):
        pipeline_label = PIPELINE_LABELS.get(pipeline, pipeline)
        badge_cls = "badge cert" if pipeline == "certification" else "badge"
        tab_id = f"tab-{project_hash}"
        panel_id = f"panel-{project_hash}"
        selected = "true" if i == 0 else "false"
        active = "true" if i == 0 else "false"
        index_link = f"{slug}/index.html"
        tabs.append(
            f'<a class="tab" id="{tab_id}" role="tab" href="#{project_hash}" '
            f'data-hash="{project_hash}" aria-selected="{selected}" '
            f'aria-controls="{panel_id}"><span>{escape(display_name)}</span></a>'
        )
        panels.append(
            f'<section class="panel" id="{panel_id}" role="tabpanel" '
            f'data-group="root" data-active="{active}" '
            f'aria-labelledby="{tab_id}">'
            f'<div class="proj-head"><h2>{escape(display_name)}</h2>'
            f'<span class="{badge_cls}">{escape(pipeline_label)}</span></div>'
            f'<p class="blurb">{escape(PIPELINE_BLURBS.get(pipeline, pipeline_label))}</p>'
            f'<a class="btn-back" href="{escape(index_link)}">'
            f'<span>查看课程目录</span></a>'
            f'</section>'
        )
    tablist = (
        f'<div class="tabs" role="tablist" data-group="root" aria-label="学习项目">'
        + "".join(tabs) + '</div>'
    )
    body = "".join(panels)
    return (
        '<!doctype html>\n'
        '<html lang="zh-CN">\n'
        '<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<title>Fyuu Tutor · 学习门户</title>\n'
        '<link rel="stylesheet" href="portal.css"></head>\n'
        '<body data-tabs-scope><main>\n'
        '<h1>Fyuu Tutor</h1>\n'
        '<p class="intro">选择一个学习项目，开始今天的课程。</p>\n'
        f'{tablist}\n'
        f'{body}\n'
        '<footer>由 Fyuu Tutor Skill 自动生成 · 仅含课件内容，不含私人数据</footer>\n'
        '</main>\n'
        '<script src="portal.js"></script>\n'
        '</body></html>\n'
    )


def write_portal_assets(out_dir: Path) -> None:
    """Write portal.css and portal.js into the staging directory (portal-only)."""
    (out_dir / "portal.css").write_text(PORTAL_CSS, encoding="utf-8")
    (out_dir / "portal.js").write_text(PORTAL_JS, encoding="utf-8")



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

    total = sum(len(p[5]) for p in portal_projects)
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
    portal_projects: list[tuple[str, str, str, str, str, list[tuple[str, str]]]] = []
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
        project_hash = PROJECT_HASH.get(pid, slug)

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
            project_index_html(display_name, pipeline, slug, project_hash, copied),
            encoding="utf-8")

        portal_projects.append((pid, pipeline, display_name, slug, project_hash, copied))
        print(f"  {display_name} ({pipeline}): {len(copied)} pages -> {slug}/")

    # Generate every public file before the final security scan.
    write_portal_assets(staging)
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
