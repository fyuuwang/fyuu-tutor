#!/usr/bin/env python3
"""Export a lesson or reference HTML as a self-contained single-file offline copy.

Inlines local lesson.css and lesson.js, keeps inline JSON question blocks,
and rejects remote styles, remote scripts, file:// dependencies, missing
assets, and non-UTF-8 content. The source file is never modified.

Usage:
    python3 export_offline_lesson.py \
        --file <project>/outputs/lessons/<lesson>.html \
        --out <destination>/<lesson>.offline.html
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.dont_write_bytecode = True

# CSS / JS reference tags we convert to inline
CSS_LINK_RE = re.compile(
    r'<link\s[^>]*\brel=["\']stylesheet["\'][^>]*\bhref=["\']([^"\']+)["\'][^>]*/?\s*>',
    re.IGNORECASE,
)
JS_SCRIPT_RE = re.compile(
    r'<script\s[^>]*\bsrc=["\']([^"\']+)["\'][^>]*>\s*</script>',
    re.IGNORECASE,
)

# Inline script blocks that must be preserved (JSON payloads, audio config).
PRESERVE_SCRIPT_IDS = {"lesson-questions", "audio-config"}


class LinkCollector(HTMLParser):
    """Parse the page once and collect all link/script references."""

    def __init__(self):
        super().__init__()
        self.css_refs: list[str] = []
        self.js_refs: list[str] = []
        self.inline_script_ids: set[str] = set()

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "link" and d.get("rel", "").lower() == "stylesheet":
            href = d.get("href", "")
            if href:
                self.css_refs.append(href)
        elif tag == "script" and "src" in d:
            self.js_refs.append(d["src"])
        elif tag == "script":
            sid = d.get("id", "")
            if sid in PRESERVE_SCRIPT_IDS:
                self.inline_script_ids.add(sid)


def sha256_file(path: Path) -> str:
    """SHA-256 of a file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export_offline(source: Path, out: Path) -> str:
    """Read a lesson HTML, inline assets, write to out. Returns SHA-256 of source."""
    source = source.resolve()
    out = out.resolve()
    if source == out:
        print("ERROR: --out must differ from --file", file=sys.stderr)
        return ""

    # Reject non-UTF-8 source
    try:
        html = source.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print("ERROR: source file is not valid UTF-8", file=sys.stderr)
        return ""
    src_hash = sha256_file(source)

    # Collect references
    collector = LinkCollector()
    collector.feed(html)

    page_dir = source.parent

    # Reject remote CSS/JS
    for href in collector.css_refs + collector.js_refs:
        lowered = href.lower()
        if lowered.startswith(("http:", "https:")):
            print(f"ERROR: remote resource rejected: {href}", file=sys.stderr)
            return ""
        if lowered.startswith("file:"):
            print(f"ERROR: file:// reference rejected: {href}", file=sys.stderr)
            return ""

    # Resolve and inline CSS
    css_text = ""
    seen_css = False
    for href in collector.css_refs:
        css_path = (page_dir / href).resolve()
        if not css_path.is_file():
            print(f"ERROR: CSS file not found: {css_path}", file=sys.stderr)
            return ""
        try:
            css_text += css_path.read_text(encoding="utf-8")
            seen_css = True
        except UnicodeDecodeError:
            print(f"ERROR: CSS file is not valid UTF-8: {css_path}", file=sys.stderr)
            return ""

    # Resolve and inline JS
    js_text = ""
    seen_js = False
    for src in collector.js_refs:
        js_path = (page_dir / src).resolve()
        if not js_path.is_file():
            print(f"ERROR: JS file not found: {js_path}", file=sys.stderr)
            return ""
        try:
            js_text += js_path.read_text(encoding="utf-8")
            seen_js = True
        except UnicodeDecodeError:
            print(f"ERROR: JS file is not valid UTF-8: {js_path}", file=sys.stderr)
            return ""

    # Replace <link rel="stylesheet"> tags with inline <style>
    if seen_css:
        html = CSS_LINK_RE.sub("", html)
        # Insert <style> before </head>
        if "</head>" in html:
            html = html.replace("</head>", f"<style>\n{css_text}\n</style>\n</head>")
        else:
            html = f"<style>\n{css_text}\n</style>\n{html}"

    # Replace <script src="..."> with inline <script>
    if seen_js:
        html = JS_SCRIPT_RE.sub("", html)
        # Insert <script> before </body>
        if "</body>" in html:
            html = html.replace("</body>", f"<script>\n{js_text}\n</script>\n</body>")
        else:
            html = f"{html}\n<script>\n{js_text}\n</script>\n"

    # Ensure all preserved inline script blocks still exist
    for sid in PRESERVE_SCRIPT_IDS:
        if sid in collector.inline_script_ids:
            if f'id="{sid}"' not in html:
                print(f"ERROR: inline script id={sid} was removed during export", file=sys.stderr)
                return ""

    # Write output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")

    # Verify source unchanged
    if sha256_file(source) != src_hash:
        print("ERROR: source file was modified during export", file=sys.stderr)
        return ""

    return src_hash


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="Source lesson HTML")
    parser.add_argument("--out", required=True, help="Output path (.offline.html recommended)")
    args = parser.parse_args()

    src = Path(args.file)
    if not src.is_file():
        print(f"ERROR: --file not found: {src}", file=sys.stderr)
        return 1

    out = Path(args.out)
    hash_val = export_offline(src, out)
    if not hash_val:
        return 1

    print(f"OK offline export: {out} (source SHA-256: {hash_val})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
