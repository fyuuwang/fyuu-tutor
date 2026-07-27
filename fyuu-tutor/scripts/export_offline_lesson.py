#!/usr/bin/env python3
"""Export one UI-kit lesson as a safe, standalone offline HTML file.

Only the project's local ``outputs/assets/lesson.css`` and ``lesson.js``
dependencies may be inlined.  This intentionally rejects media, inline CSS,
and every other URL-bearing feature: the current UI kit does not need them,
and accepting them would make a single-file export difficult to verify.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

sys.dont_write_bytecode = True

CSS_IMPORT_RE = re.compile(r"@import\b", re.IGNORECASE)
CSS_URL_RE = re.compile(r"\burl\s*\(", re.IGNORECASE)
CSS_IMAGE_SET_RE = re.compile(r"\bimage-set\s*\(", re.IGNORECASE)
CSS_PROTOCOL_RE = re.compile(r"\b(?:https?|file|data):", re.IGNORECASE)
ALLOWED_SCRIPT_IDS = {"lesson-questions", "audio-config"}

# Any element bearing one of these attributes can load or submit another
# document.  Reject by attribute, not by a fragile list of element names.
LOAD_ATTRS = {
    "src", "srcset", "imagesrcset", "poster", "data", "action", "formaction", "srcdoc",
    "background", "xlink:href", "ping", "attributionsrc", "manifest", "codebase", "archive",
    "classid", "cite", "longdesc",
}


class ExportRewriter(HTMLParser):
    """One parser for both validation collection and HTML rewriting."""

    def __init__(self, *, allow_inline_style: bool = False,
                 allow_generated_inline_scripts: bool = False) -> None:
        super().__init__(convert_charrefs=False)
        self.out: list[str] = []
        self.css_hrefs: list[str] = []
        self.js_srcs: list[str] = []
        self.violations: list[str] = []
        self.inline_script_ids: set[str] = set()
        self._skip_script = False
        self._capture_audio_config = False
        self._audio_config_parts: list[str] = []
        self._allow_inline_style = allow_inline_style
        self._allow_generated_inline_scripts = allow_generated_inline_scripts

    def _raw_starttag(self) -> str:
        return self.get_starttag_text() or ""

    def _record_forbidden_attrs(self, tag: str, attrs: dict[str, str | None], *, allow_href: bool = False,
                                allowed_load_attrs: frozenset[str] = frozenset()) -> None:
        if "style" in attrs:
            self.violations.append(f"inline style attribute not allowed on <{tag}>")
        for attr, value in attrs.items():
            lower_attr = attr.lower()
            if attr.lower().startswith("on"):
                self.violations.append(f"event handler not allowed: <{tag} {attr}=...>")
            if lower_attr in LOAD_ATTRS and lower_attr not in allowed_load_attrs and value is not None:
                self.violations.append(f"resource attribute not allowed: <{tag} {attr}=...>")
            if lower_attr == "href" and tag != "a" and not allow_href and value is not None:
                self.violations.append(f"resource href not allowed: <{tag} href=...>")
            if lower_attr == "href" and isinstance(value, str):
                compact = "".join(value.split()).lower()
                if compact.startswith(("javascript:", "data:")):
                    self.violations.append(f"active href not allowed: <{tag} {attr}=...>")

    def _handle_start(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        names = [attr.lower() for attr, _ in attrs]
        if len(names) != len(set(names)):
            self.violations.append(f"duplicate attribute not allowed on <{tag}>")
        values = dict(attrs)
        name = tag.lower()

        if self._skip_script:
            return

        if name == "link":
            self._record_forbidden_attrs(name, values, allow_href=True)
            href = values.get("href")
            if href is not None:
                if values.get("rel", "").lower() == "stylesheet" and href:
                    self.css_hrefs.append(href)
                else:
                    self.violations.append("non-stylesheet <link href> not allowed")
            self.out.append(self._raw_starttag() if href is None else "")
            return

        if name == "script":
            self._record_forbidden_attrs(name, values, allowed_load_attrs=frozenset({"src"}))
            if "src" in values:
                src = values.get("src")
                if src:
                    self.js_srcs.append(src)
                    self._skip_script = True
                else:
                    self.violations.append("empty script src not allowed")
                return
            script_id = values.get("id") or ""
            if self._allow_generated_inline_scripts and not script_id:
                self.out.append(self._raw_starttag())
                return
            if script_id not in ALLOWED_SCRIPT_IDS or values.get("type") != "application/json":
                self.violations.append("only application/json lesson-questions or audio-config scripts are allowed")
                self.out.append(self._raw_starttag())
                return
            self.inline_script_ids.add(script_id)
            self.out.append(self._raw_starttag())
            if script_id == "audio-config":
                self._capture_audio_config = True
            return

        self._record_forbidden_attrs(name, values)
        if name == "style":
            if not self._allow_inline_style:
                self.violations.append("inline <style> not allowed")
        elif name == "base" and "href" in values:
            self.violations.append("<base href> not allowed")
        elif name == "meta" and (values.get("http-equiv") or "").strip().lower() == "refresh":
            self.violations.append("meta refresh not allowed")
        elif name == "svg":
            self.violations.append("inline SVG not allowed in offline export")

        self.out.append(self._raw_starttag())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._handle_start(tag, attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # HTMLParser's default calls start + end, which would leave </link>
        # behind after an inlined self-closing stylesheet.  Preserve or drop it
        # exactly once here.
        self._handle_start(tag, attrs)
        if self._skip_script and tag.lower() == "script":
            self._skip_script = False

    def handle_endtag(self, tag: str) -> None:
        if self._skip_script:
            if tag.lower() == "script":
                self._skip_script = False
            return
        if self._capture_audio_config and tag.lower() == "script":
            try:
                config = json.loads("".join(self._audio_config_parts))
            except json.JSONDecodeError:
                self.violations.append("audio-config must be valid JSON")
                config = {}
            if not isinstance(config, dict):
                self.violations.append("audio-config must be a JSON object")
                config = {}
            # An offline export may use native speech synthesis, but never a
            # configured network TTS service or online dictionary fallback.
            offline_config = {"allow_remote_tts": False}
            if isinstance(config.get("lang"), str):
                offline_config["lang"] = config["lang"]
            self.out.append(json.dumps(offline_config, ensure_ascii=False, separators=(",", ":")))
            self.out.append(f"</{tag}>")
            self._capture_audio_config = False
            self._audio_config_parts = []
            return
        self.out.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self._capture_audio_config:
            self._audio_config_parts.append(data)
        elif not self._skip_script:
            self.out.append(data)

    def handle_entityref(self, name: str) -> None:
        text = f"&{name};"
        if self._capture_audio_config:
            self._audio_config_parts.append(text)
        elif not self._skip_script:
            self.out.append(text)

    def handle_charref(self, name: str) -> None:
        text = f"&#{name};"
        if self._capture_audio_config:
            self._audio_config_parts.append(text)
        elif not self._skip_script:
            self.out.append(text)

    def handle_comment(self, data: str) -> None:
        if not self._skip_script:
            self.out.append(f"<!--{data}-->")

    def handle_decl(self, decl: str) -> None:
        if not self._skip_script:
            self.out.append(f"<!{decl}>")

    def handle_pi(self, data: str) -> None:
        if not self._skip_script:
            self.out.append(f"<?{data}>")

    def rewritten_html(self) -> str:
        return "".join(self.out)

    def finish(self) -> None:
        if self._capture_audio_config:
            self.violations.append("unterminated audio-config script")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _find_assets_root(source: Path) -> Path | None:
    for parent in source.parents:
        if parent.name == "outputs":
            assets = parent / "assets"
            if assets.is_dir() and not assets.is_symlink():
                return assets.resolve()
            return None
    return None


def _safe_asset_path(ref: str, page_dir: Path, assets_root: Path) -> Path | None:
    """Resolve one CSS/JS reference only when it is a local asset-root file."""
    if ref != ref.strip() or "\\" in ref:
        return None
    parts = urlsplit(ref)
    if parts.scheme or parts.netloc or parts.query or parts.fragment or not parts.path:
        return None
    path = Path(parts.path)
    if path.is_absolute():
        return None
    raw = page_dir / path
    try:
        check = raw
        while True:
            if check.is_symlink():
                return None
            parent = check.parent
            if parent == check:
                break
            check = parent
        resolved = raw.resolve()
        resolved.relative_to(assets_root)
    except (OSError, ValueError):
        return None
    return resolved if resolved.is_file() and not resolved.is_symlink() else None


def _safe_css(css: str, label: str) -> str | None:
    # The UI kit contains no CSS escapes, imports, or url() values.  Rejecting
    # all three avoids an incomplete CSS parser and is deliberately fail-closed.
    if _has_css_escape_outside_string_or_comment(css):
        return f"{label}: CSS escapes are not allowed"
    if CSS_IMPORT_RE.search(css):
        return f"{label}: CSS @import not allowed"
    if CSS_URL_RE.search(css):
        return f"{label}: CSS url() not allowed"
    if CSS_IMAGE_SET_RE.search(css):
        return f"{label}: CSS image-set() not allowed"
    if CSS_PROTOCOL_RE.search(css):
        return f"{label}: CSS protocol reference not allowed"
    if "</style" in css.lower():
        return f"{label}: CSS style-tag terminator not allowed"
    return None


def _has_css_escape_outside_string_or_comment(css: str) -> bool:
    """Reject identifier escapes while allowing quoted content such as "\\2212"."""
    quote: str | None = None
    i = 0
    while i < len(css):
        if quote:
            if css[i] == "\\":
                i += 2
                continue
            if css[i] == quote:
                quote = None
            i += 1
            continue
        if css.startswith("/*", i):
            end = css.find("*/", i + 2)
            i = len(css) if end == -1 else end + 2
            continue
        if css[i] in {"'", '"'}:
            quote = css[i]
        elif css[i] == "\\":
            return True
        i += 1
    return False


def _asset_error(kind: str, ref: str) -> str:
    parts = urlsplit(ref.strip())
    if parts.scheme in {"http", "https"} or parts.netloc:
        return f"remote {kind} not allowed: {ref}"
    if parts.scheme == "file":
        return f"file:// {kind} not allowed: {ref}"
    return f"{kind} reference outside allowed assets root: {ref}"


def _load_assets(refs: list[str], kind: str, page_dir: Path, assets_root: Path) -> tuple[str, str | None]:
    expected_name = "lesson.css" if kind == "CSS" else "lesson.js"
    parts: list[str] = []
    for ref in refs:
        path = _safe_asset_path(ref, page_dir, assets_root)
        if path is None:
            return "", _asset_error(kind, ref)
        if path.name != expected_name:
            return "", f"only {expected_name} may be inlined (found {path.name})"
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return "", f"{kind} file is not valid UTF-8: {path}"
        if kind == "CSS":
            css_error = _safe_css(content, f"CSS file {path.name}")
            if css_error:
                return "", css_error
        parts.append(content)
    return "\n".join(parts), None


def export_offline(source: Path, out: Path) -> str:
    """Create one offline export; return source SHA-256 or an empty string."""
    if source.is_symlink():
        print("ERROR: source symlink not allowed", file=sys.stderr)
        return ""
    source = source.resolve()
    out = out.resolve()
    if source == out:
        print("ERROR: --out must differ from --file", file=sys.stderr)
        return ""

    try:
        html = source.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"ERROR: cannot read UTF-8 source: {exc}", file=sys.stderr)
        return ""
    source_hash = sha256_file(source)
    assets_root = _find_assets_root(source)
    if assets_root is None:
        print("ERROR: could not locate project outputs/assets/ directory", file=sys.stderr)
        return ""

    rewriter = ExportRewriter()
    rewriter.feed(html)
    rewriter.close()
    rewriter.finish()
    if rewriter.violations:
        print(f"ERROR: {rewriter.violations[0]}", file=sys.stderr)
        return ""

    css, error = _load_assets(rewriter.css_hrefs, "CSS", source.parent, assets_root)
    if error:
        print(f"ERROR: {error}", file=sys.stderr)
        return ""
    js, error = _load_assets(rewriter.js_srcs, "JS", source.parent, assets_root)
    if error:
        print(f"ERROR: {error}", file=sys.stderr)
        return ""

    rewritten = rewriter.rewritten_html()
    for script_id in rewriter.inline_script_ids:
        if f'id="{script_id}"' not in rewritten:
            print(f"ERROR: inline script id={script_id} was removed", file=sys.stderr)
            return ""
    if css:
        rewritten = rewritten.replace("</head>", f"<style>\n{css}\n</style>\n</head>", 1)
    if js:
        rewritten = rewritten.replace("</body>", f"<script>\n{js}\n</script>\n</body>", 1)

    # Reparse the completed export.  This catches a future rewriter change or
    # malformed asset content that leaves a loadable resource in the output.
    post = ExportRewriter(allow_inline_style=True, allow_generated_inline_scripts=True)
    post.feed(rewritten)
    post.close()
    post.finish()
    if post.violations or post.css_hrefs or post.js_srcs:
        detail = (post.violations or ["external CSS or JS survived export"])[0]
        print(f"ERROR: output verification failed: {detail}", file=sys.stderr)
        return ""

    # Check before creating anything.  Write a sibling temporary file and only
    # replace an existing destination after the final source-hash check.
    if sha256_file(source) != source_hash:
        print("ERROR: source file changed during export", file=sys.stderr)
        return ""
    temp_path: Path | None = None
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=out.parent,
                                         prefix=f".{out.name}.", suffix=".tmp", delete=False) as tmp:
            temp_path = Path(tmp.name)
            tmp.write(rewritten)
        if sha256_file(source) != source_hash:
            temp_path.unlink(missing_ok=True)
            print("ERROR: source file changed during export", file=sys.stderr)
            return ""
        temp_path.replace(out)
    except OSError as exc:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        print(f"ERROR: cannot write output: {exc}", file=sys.stderr)
        return ""
    return source_hash


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="source lesson HTML")
    parser.add_argument("--out", required=True, help="destination .offline.html")
    args = parser.parse_args()
    source = Path(args.file)
    if not source.is_file():
        print(f"ERROR: --file not found: {source}", file=sys.stderr)
        return 1
    source_hash = export_offline(source, Path(args.out))
    if not source_hash:
        return 1
    print(f"OK offline export: {args.out} (source SHA-256: {source_hash})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
