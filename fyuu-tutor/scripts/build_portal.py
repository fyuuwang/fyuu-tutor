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
import json
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
REFERENCE_PREFIX = "ref-"

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
# Falls back to the public URL slug when an id is not listed here.
PROJECT_HASH = {
    "pmp-certification": "pmp",
    "business-cantonese": "cantonese",
    "ai-systems-designer": "ai",
}

# Public routes are English, short, and independent of a learner's private
# directory or localized display name.  New projects fall back to their
# ASCII project_id; non-ASCII project IDs are rejected for public publishing.
PROJECT_PUBLIC_SLUG = {
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
PIPELINE_THEME = {"capability": "overview", "certification": "business", "language": "people"}
UI_KIT_TOKENS = Path(__file__).resolve().parents[1] / "assets" / "ui-kit" / "assets" / "tokens.css"

PORTAL_LAYOUT_CSS = """\
*{box-sizing:border-box}body{margin:0;background:var(--page);color:var(--ink);font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif}main{width:min(calc(100% - 32px),var(--content));margin:32px auto 64px;padding:clamp(24px,5vw,48px);background:var(--surface);border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow)}h1{margin:0 0 8px;font-size:clamp(30px,5vw,46px);line-height:1.25}h2{margin:0;font-size:22px;line-height:1.35}.muted,.intro,.blurb{color:var(--ink-soft)}.intro{margin:0 0 28px}.project-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.project-card{display:flex;min-height:164px;flex-direction:column;justify-content:space-between;padding:20px;border:1px solid var(--line);border-left:4px solid var(--indigo);border-radius:var(--radius);background:var(--surface-soft);color:inherit;text-decoration:none}.project-card:hover,.project-card:focus-visible{border-color:var(--indigo);box-shadow:0 10px 28px rgba(23,32,51,.08)}.project-card .project-name{font-size:20px;font-weight:700}.project-card .project-kind{font-size:13px;color:var(--indigo-dark);font-weight:650}.project-card p{margin:10px 0 0;color:var(--ink-soft);font-size:14px}.route-head{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:4px}.route-head h1{font-size:clamp(28px,4vw,38px)}.badge{display:inline-flex;align-items:center;min-height:28px;padding:3px 9px;border:1px solid var(--line);border-radius:999px;background:var(--indigo-soft);color:var(--indigo-dark);font-size:12px;font-weight:650}.course-return-dock{position:fixed;right:max(16px,env(safe-area-inset-right));bottom:max(16px,env(safe-area-inset-bottom));z-index:15;display:inline-grid;grid-auto-flow:column;overflow:hidden;border:1px solid var(--line);border-radius:999px;background:rgba(255,255,255,.96);box-shadow:var(--shadow)}.course-return-dock a{display:inline-flex;align-items:center;justify-content:center;min-width:48px;min-height:48px;padding:10px;color:var(--ink-soft);font-size:20px;text-decoration:none}.course-return-dock a:hover,.course-return-dock a:focus-visible{background:var(--indigo-soft);color:var(--indigo-dark)}.course-return-dock a:focus-visible{outline:2px solid var(--indigo);outline-offset:-2px}.course-return-label{position:absolute;width:1px;height:1px;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap}.tabs{display:flex;gap:0;margin:28px 0 20px;border-bottom:1px solid var(--line)}.tab{display:flex;align-items:center;justify-content:center;min-height:52px;flex:1;padding:10px 12px;border-bottom:3px solid transparent;color:var(--ink-soft);text-decoration:none;font-weight:650;text-align:center}.tab[aria-selected="true"]{color:var(--indigo-dark);border-bottom-color:var(--indigo)}.tab .count{margin-left:6px;font-size:12px;font-weight:600;opacity:.8}.js .panel{display:none}.js .panel[data-active="true"]{display:block}.catalog-heading{margin:28px 0 14px;font-size:18px}.entries{display:grid;gap:10px}.entry{display:flex;align-items:center;gap:12px;min-height:52px;padding:12px 14px;border:1px solid var(--line);border-radius:var(--radius);background:var(--surface-soft);color:inherit;text-decoration:none}.entry:hover,.entry:focus-visible{border-color:var(--indigo);background:var(--indigo-soft)}.entry .num{flex:0 0 auto;min-width:42px;font-variant-numeric:tabular-nums;font-weight:700;color:var(--indigo-dark)}.entry .tag{flex:0 0 auto;padding:2px 8px;border:1px solid var(--line);border-radius:999px;color:var(--ink-soft);font-size:11px;font-weight:650}.entry .title{flex:1;line-height:1.4}.package{margin:18px 0;padding:16px;border:1px solid var(--line);border-left:4px solid var(--indigo);border-radius:var(--radius);background:var(--surface)}.package-head{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;margin-bottom:12px}.package-number{color:var(--indigo-dark);font-weight:700;font-variant-numeric:tabular-nums}.package-meta{color:var(--ink-soft);font-size:13px}.package .entries{margin-left:8px}.package .entry{background:var(--surface-soft)}.empty{padding:18px;border:1px dashed var(--line);border-radius:var(--radius);color:var(--ink-soft);text-align:center}footer{margin-top:48px;padding-top:20px;border-top:1px solid var(--line);color:var(--ink-soft);font-size:13px}@media(max-width:680px){main{margin:16px auto 104px;padding:24px 18px}.project-grid{grid-template-columns:1fr}.project-card{min-height:128px}.tabs{overflow-x:auto}.tab{min-width:110px}.entry .num{min-width:34px}.package{padding:14px}.package .entries{margin-left:0}.course-return-dock{right:max(12px,env(safe-area-inset-right));bottom:max(12px,env(safe-area-inset-bottom))}}
"""

# Hash + keyboard tab switching shared by the root portal and every project
# catalog. When JS is unavailable, every panel stays in source order and all
# links remain reachable (no hidden-by-default content).
PORTAL_JS = """\
(function () {
  // Progressive enhancement: hide non-active panels only when JS runs.
  // Without JS the class is never added, so every panel stays visible and
  // all project/lesson links remain reachable in source order.
  var root = document.documentElement;
  root.classList.add('js');
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


def public_slug(project_id: str) -> str:
    """Return the stable ASCII route for one public project."""
    if project_id in PROJECT_PUBLIC_SLUG:
        return PROJECT_PUBLIC_SLUG[project_id]
    if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", project_id):
        return project_id
    raise ValueError(f"project_id has no safe public ASCII route: {project_id!r}")


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


def _rewrite_flattened_page(text: str, *, reference: bool) -> str:
    """Adapt one copied page from local outputs/ to its flat public route."""
    replacements = {
        'href="../assets/lesson.css"': 'href="assets/lesson.css"',
        "href='../assets/lesson.css'": "href='assets/lesson.css'",
        'src="../assets/lesson.js"': 'src="assets/lesson.js"',
        "src='../assets/lesson.js'": "src='assets/lesson.js'",
        'href="../index.html"': 'href="index.html"',
        "href='../index.html'": "href='index.html'",
        'href="../../../index.html"': 'href="../index.html"',
        "href='../../../index.html'": "href='../index.html'",
        'href="../../../../index.html"': 'href="../index.html"',
        "href='../../../../index.html'": "href='../index.html'",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    text = re.sub(r"<body\b", '<body data-portal-home="../index.html" data-course-route="index.html"', text, count=1, flags=re.IGNORECASE)
    if reference:
        def rewrite_sibling_reference(match: re.Match[str]) -> str:
            target = match.group(2)
            if target == "index.html":
                return match.group(1) + target + match.group(3)
            return match.group(1) + REFERENCE_PREFIX + target + match.group(3)
        text = re.sub(r'(\bhref\s*=\s*["\'])([^/"\'#?]+\.html)(["\'])',
                      rewrite_sibling_reference, text)
    text = re.sub(r'(["\'])\.\./lessons/([^/"\'#?]+\.html)(\1)',
                  r'\1\2\3', text)
    text = re.sub(r'(["\'])\.\./reference/([^/"\'#?]+\.html)(\1)',
                  rf'\1{REFERENCE_PREFIX}\2\3', text)
    return text


def copy_whitelisted(project_root: Path, dest: Path) -> list[tuple[str, str]]:
    """Copy approved public files and return [(public_href, title)].

    Lesson files are published as ``<project>/<lesson>.html`` and reference
    aids as ``<project>/ref-<aid>.html``. Source HTML stays untouched: only
    copied pages have local asset, catalog, and cross-category links rewritten.
    """
    outputs = project_root / "outputs"
    if not outputs.is_dir():
        print(f"WARNING: no outputs/ in {project_root.name}", file=sys.stderr)
        return []

    pages: list[tuple[str, str]] = []

    public_hrefs: set[str] = set()
    for sub in ALLOWED_HTML_SUBDIRS:
        subdir = outputs / sub
        if not subdir.is_dir():
            continue
        for html in sorted(subdir.rglob("*.html")):
            if not is_symlink_safe(html):
                raise RuntimeError(f"symlink detected: {html}")
            if not re.fullmatch(r"[a-z0-9][a-z0-9.-]*\.html", html.name):
                raise RuntimeError(
                    f"public page filename must be lowercase ASCII: {html.name}")
            if sub == "lessons":
                rel = Path(html.name)
            else:
                rel = Path(REFERENCE_PREFIX + html.name)
            public_href = str(rel).replace("\\", "/")
            if public_href == "index.html" or public_href in public_hrefs:
                raise RuntimeError(f"public route collision: {public_href}")
            public_hrefs.add(public_href)
            out_file = dest / rel
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(_rewrite_flattened_page(
                html.read_text(encoding="utf-8"), reference=(sub == "reference")),
                encoding="utf-8")
            pages.append((public_href, page_title(html)))

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
      - ref-* -> reference
      - flat page names containing `review` or whose title contains 复习 -> review
      - remaining flat pages -> lessons
    """
    if href.startswith(REFERENCE_PREFIX):
        return "reference"
    name = href.rsplit("/", 1)[-1]
    if "review" in name.lower() or "复习" in title:
        return "review"
    return "lessons"


def sort_pages(pages: list[tuple[str, str]], category: str) -> list[tuple[str, str]]:
    """Stable order within a catalog category.

    Lessons/review: leading number, then trailing letter, then filename.
    Reference: by path then title.
    """
    if category in ("lessons", "review"):
        return sorted(pages, key=lambda ht: _leading_number(ht[0]))
    return sorted(pages, key=lambda ht: (ht[0], ht[1]))


def _course_label(href: str) -> str:
    """Return a stable learner-facing number, never a transient list index."""
    number, suffix, _ = _leading_number(href)
    return f"{number:02d}{suffix.upper()}" if number < 10 ** 9 else "课"


def _entry_html(href: str, title: str, label: str, tag: str) -> str:
    """A single compact, clickable catalog row (>=44px tap target)."""
    return (
        f'<a class="entry" href="{escape(href)}">'
        f'<span class="num">{escape(label)}</span>'
        f'<span class="tag">{escape(tag)}</span>'
        f'<span class="title">{escape(title)}</span>'
        f'</a>'
    )


def _entries_html(items: list[tuple[str, str]], tag: str) -> str:
    if not items:
        return ""
    rows = "".join(_entry_html(h, t, _course_label(h), tag) for h, t in items)
    return f'<div class="entries">{rows}</div>'


def load_catalog_groups(project_root: Path, lessons: list[tuple[str, str]]) -> list[dict]:
    """Read optional public-safe micro-lesson package metadata."""
    path = project_root / "outputs" / "catalog.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid public catalog manifest: {path}: {exc}") from exc
    if data.get("schema_version") != 1 or not isinstance(data.get("groups"), list):
        raise RuntimeError(f"invalid public catalog manifest schema: {path}")
    available = dict(lessons)
    groups: list[dict] = []
    seen: set[str] = set()
    for group in data["groups"]:
        if (not isinstance(group, dict) or not all(isinstance(group.get(k), str) and group[k] for k in ("id", "title"))
                or not re.fullmatch(r"\d{4}", group["id"])):
            raise RuntimeError(f"invalid public catalog group in {path}")
        parts = group.get("parts")
        if not isinstance(parts, list) or not parts:
            raise RuntimeError(f"invalid public catalog parts for {group['id']}")
        shown = []
        for part in parts:
            if not isinstance(part, dict) or not all(isinstance(part.get(k), str) and part[k] for k in ("id", "title", "href")):
                raise RuntimeError(f"invalid public catalog part for {group['id']}")
            href = part["href"]
            if href in seen:
                raise RuntimeError(f"duplicate public catalog part: {href}")
            if href in available:
                seen.add(href)
                shown.append({"href": href, "id": part["id"], "title": part["title"]})
        if shown:
            groups.append({"id": group["id"], "title": group["title"], "parts": shown, "total": len(parts)})
    return groups


def _lesson_entries_html(items: list[tuple[str, str]], groups: list[dict]) -> str:
    """Render standalone lessons and optional package groups in learning order."""
    grouped = {part["href"] for group in groups for part in group["parts"]}
    blocks = []
    for href, title in items:
        if href not in grouped:
            blocks.append((_leading_number(href), _entry_html(href, title, _course_label(href), "课程")))
    for group in groups:
        rows = "".join(_entry_html(part["href"], part["title"], part["id"][-1], "微课") for part in group["parts"])
        count = f"{len(group['parts'])}/{group['total']} 个微课已上线"
        html = (
            '<section class="package">'
            f'<div class="package-head"><span class="package-number">第 {int(group["id"]):02d} 课</span>'
            f'<strong>{escape(group["title"])}</strong><span class="package-meta">{count}</span></div>'
            f'<div class="entries">{rows}</div></section>'
        )
        blocks.append((_leading_number(group["id"] + ".html"), html))
    return "".join(html for _, html in sorted(blocks, key=lambda item: item[0]))


def lesson_route_order(items: list[tuple[str, str]], groups: list[dict]) -> list[str]:
    """Return public lesson hrefs in the same order as the visible route."""
    grouped = {part["href"] for group in groups for part in group["parts"]}
    blocks = [(_leading_number(href), [href]) for href, _ in items if href not in grouped]
    blocks.extend((_leading_number(group["id"] + ".html"), [part["href"] for part in group["parts"]]) for group in groups)
    return [href for _, hrefs in sorted(blocks, key=lambda item: item[0]) for href in hrefs]


def add_public_lesson_navigation(dest: Path, order: list[str]) -> None:
    """Add previous/next links only to copied public lesson pages."""
    for index, href in enumerate(order):
        path = dest / href
        if not path.is_file():
            continue
        links = []
        if index:
            links.append(f'<a href="{escape(order[index - 1])}">← 上一节</a>')
        if index + 1 < len(order):
            links.append(f'<a href="{escape(order[index + 1])}">继续下一节 →</a>')
        if not links:
            continue
        text = path.read_text(encoding="utf-8")
        if 'class="course-pagination"' in text:
            continue
        text = text.replace("</footer>", f'<nav class="course-pagination" aria-label="课程前后导航">{"".join(links)}</nav></footer>', 1)
        path.write_text(text, encoding="utf-8")


def project_index_html(display_name: str, pipeline: str, slug: str,
                       project_hash: str,
                       pages: list[tuple[str, str]], catalog_groups: list[dict]) -> str:
    """Generate a public per-project catalog, no STATUS data."""
    pipeline_label = PIPELINE_LABELS.get(pipeline, pipeline)
    buckets: dict[str, list[tuple[str, str]]] = {c: [] for c in TAB_HASH}
    for href, title in pages:
        buckets[classify_page(href, title)].append((href, title))
    for cat in TAB_HASH:
        buckets[cat] = sort_pages(buckets[cat], cat)

    visible = [cat for cat in TAB_HASH if buckets[cat]]
    if len(visible) == 1:
        cat = visible[0]
        content = _lesson_entries_html(buckets[cat], catalog_groups) if cat == "lessons" else _entries_html(buckets[cat], TAB_LABELS[cat])
        tablist = ""
        body = f'<h2 class="catalog-heading">{TAB_LABELS[cat]}路线</h2>{content}'
    elif not visible:
        tablist = ""
        body = '<p class="empty">尚未发布课程</p>'
    else:
        tabs = []
        panels = []
        for i, cat in enumerate(visible):
            tab_id = f"tab-{cat}"
            panel_id = f"panel-{cat}"
            selected = "true" if i == 0 else "false"
            active = "true" if i == 0 else "false"
            count = len(buckets[cat])
            tab = (
                f'<a class="tab" id="{tab_id}" role="tab" href="#{cat}" '
                f'data-hash="{cat}" aria-selected="{selected}" '
                f'aria-controls="{panel_id}">'
                f'<span>{TAB_LABELS[cat]}</span>'
                f'<span class="count">{count}</span></a>'
            )
            tabs.append(tab)
            content = _lesson_entries_html(buckets[cat], catalog_groups) if cat == "lessons" else _entries_html(buckets[cat], TAB_LABELS[cat])
            panels.append(
                f'<div class="panel" id="{panel_id}" role="tabpanel" '
                f'data-group="catalog" data-active="{active}" '
                f'aria-labelledby="{tab_id}">'
                f'{content}</div>'
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
        f'<body data-theme="{PIPELINE_THEME.get(pipeline, "overview")}" data-tabs-scope><main>\n'
        f'<div class="proj-head"><h1>{escape(display_name)}</h1>\n'
        f'<span class="{badge_cls}">{escape(pipeline_label)}</span></div>\n'
        f'<p class="blurb">{escape(PIPELINE_BLURBS.get(pipeline, pipeline_label))}</p>\n'
        f'{tablist}\n'
        f'{body}\n'
        '<footer>由 Fyuu Tutor Skill 自动生成 · 仅含课件内容</footer>\n'
        '</main>\n'
        '<nav class="course-return-dock" aria-label="全局学习导航">'
        '<a class="course-home" href="../index.html" aria-label="返回学习门户" title="学习门户">'
        '<span aria-hidden="true">⌂</span><span class="course-return-label">学习门户</span></a></nav>\n'
        '<script src="../portal.js"></script>\n'
        '</body></html>\n'
    )


def portal_html(projects: list[tuple[str, str, str, str, str, list[tuple[str, str]]]]) -> str:
    """Root portal: direct project destinations, never an extra tab layer."""
    ordered = sorted(projects, key=lambda p: (PROJECT_ORDER.get(p[0], 100), p[0]))
    cards = []
    for pid, pipeline, display_name, slug, _project_hash, pages in ordered:
        pipeline_label = PIPELINE_LABELS.get(pipeline, pipeline)
        index_link = f"{slug}/index.html"
        cards.append(
            f'<a class="project-card" data-theme="{PIPELINE_THEME.get(pipeline, "overview")}" href="{escape(index_link)}">'
            f'<div><span class="project-kind">{escape(pipeline_label)}</span><div class="project-name">{escape(display_name)}</div>'
            f'<p>{escape(PIPELINE_BLURBS.get(pipeline, pipeline_label))}</p></div>'
            f'<span class="project-kind">进入学习路线 · {len(pages)} 项内容</span></a>'
        )
    return (
        '<!doctype html>\n'
        '<html lang="zh-CN">\n'
        '<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<title>Fyuu Tutor · 学习门户</title>\n'
        '<link rel="stylesheet" href="portal.css"></head>\n'
        '<body><main>\n'
        '<h1>学习门户</h1>\n'
        '<p class="intro">选择一个学习项目，直接进入它的学习路线。</p>\n'
        f'<div class="project-grid">{"".join(cards)}</div>\n'
        '<footer>由 Fyuu Tutor Skill 自动生成 · 仅含课件内容，不含私人数据</footer>\n'
        '</main>\n'
        '<script src="portal.js"></script>\n'
        '</body></html>\n'
    )


def write_portal_assets(out_dir: Path) -> None:
    """Write portal assets with the same primitive tokens as the lesson UI."""
    (out_dir / "portal.css").write_text(
        UI_KIT_TOKENS.read_text(encoding="utf-8") + "\n" + PORTAL_LAYOUT_CSS,
        encoding="utf-8")
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
        try:
            slug = public_slug(pid)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return [], False
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
        lesson_pages = [
            (href, title) for href, title in copied if classify_page(href, title) == "lessons"
        ]
        catalog_groups = load_catalog_groups(project_root, lesson_pages)
        add_public_lesson_navigation(proj_dest, lesson_route_order(sort_pages(lesson_pages, "lessons"), catalog_groups))
        (proj_dest / "index.html").write_text(
            project_index_html(display_name, pipeline, slug, project_hash, copied, catalog_groups),
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
