#!/usr/bin/env python3
"""Validate Fyuu Tutor UI v2 HTML. Data-driven from ui-spec.json."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path

CLASS_RE = re.compile(r"(?<![-\w])\.([A-Za-z_][\w-]*)")
V1_QUESTION_RE = re.compile(r"window\.LESSON_QUESTIONS\s*=\s*\[")
JSON_QUESTION_RE = re.compile(r'type="application/json"')


def load_spec(script_dir: Path) -> dict:
    """Load ui-spec.json from the skill or project directory."""
    candidates = [
        script_dir / "assets" / "ui-kit" / "ui-spec.json",  # skill layout
        script_dir / "outputs" / "ui" / "ui-spec.json",      # project layout
        script_dir / "ui-spec.json",                            # kit root
    ]
    for spec_path in candidates:
        if spec_path.is_file():
            return json.loads(spec_path.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"ui-spec.json not found in: {[str(c) for c in candidates]}")


def spec_formats(spec: dict) -> set[str]:
    return set(spec.get("formats", {}).keys())


def spec_themes(spec: dict) -> set[str]:
    themes = spec.get("themes", {})
    return {k for k in themes if k != "recommendations"}


def spec_pipelines(spec: dict) -> set[str]:
    return set(spec.get("pipelines", {}).keys())


def spec_components(spec: dict) -> dict:
    return spec.get("components", {})


def spec_required_classes(spec: dict, fmt: str) -> set[str]:
    fmt_def = spec.get("formats", {}).get(fmt, {})
    return set(fmt_def.get("required_classes", []))


class LessonParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.body_attrs: dict[str, str] = {}
        self.classes: set[str] = set()
        self.ids: list[str] = []
        self.fragments: list[str] = []
        self.headings: list[tuple[int, str]] = []
        self.styles = 0
        self.inline_styles: list[str] = []
        self.remote_resources: list[str] = []
        self.stylesheets: list[str] = []
        self.external_scripts: list[str] = []
        self.inline_scripts: list[str] = []
        self.json_scripts: list[str] = []
        self.buttons_without_type: list[str] = []
        self._script_parts: list[str] | None = None
        self._script_type: str = ""
        self.json_script_ids: list[str] = []
        self.external_links: list[str] = []
        self.external_link_rels: list[str] = []
        self.production_task_ids: list[str] = []
        self._script_id: str = ""

    def handle_starttag(self, tag, attrs_list):
        attrs = {k: v or "" for k, v in attrs_list}
        if tag == "body":
            self.body_attrs = attrs
        if tag == "style":
            self.styles += 1
        if "style" in attrs:
            self.inline_styles.append(tag)
        if attrs.get("class"):
            self.classes.update(attrs["class"].split())
        if attrs.get("id"):
            self.ids.append(attrs["id"])
        if attrs.get("href", "").startswith("#") and len(attrs["href"]) > 1:
            self.fragments.append(attrs["href"][1:])
        href_val = attrs.get("href", "")
        if re.match(r"^https?:", href_val):
            self.external_links.append(href_val)
            self.external_link_rels.append(attrs.get("rel", ""))
        if attrs.get("class") and "production-task" in attrs["class"].split():
            iid = attrs.get("data-item-id", "")
            if iid:
                self.production_task_ids.append(iid)
            else:
                self.production_task_ids.append("")
        if tag == "link" and attrs.get("rel") == "stylesheet":
            self.stylesheets.append(attrs.get("href", ""))
        if tag == "script":
            src = attrs.get("src")
            stype = attrs.get("type", "")
            if src:
                self.external_scripts.append(src)
            elif stype == "application/json":
                self._script_parts = []
                self._script_type = "json"
                self._script_id = attrs.get("id", "")
            else:
                self._script_parts = []
                self._script_type = "js"
        if tag == "button" and not attrs.get("type"):
            self.buttons_without_type.append(attrs.get("id") or attrs.get("class") or "button")
        if re.fullmatch(r"h[1-6]", tag):
            self.headings.append((int(tag[1]), attrs.get("id", "")))
        for attr in ("href", "src"):
            value = attrs.get(attr, "")
            if re.match(r"^(?:https?:)?//", value):
                self.remote_resources.append(value)

    def handle_endtag(self, tag):
        if tag == "script" and self._script_parts is not None:
            content = "".join(self._script_parts)
            if self._script_type == "json":
                self.json_scripts.append(content)
                self.json_script_ids.append(self._script_id)
            else:
                self.inline_scripts.append(content)
            self._script_parts = None
            self._script_type = ""
            self._script_id = ""

    def handle_data(self, data):
        if self._script_parts is not None:
            self._script_parts.append(data)


def allowed_classes(css_path: Path) -> set[str]:
    classes: set[str] = set()
    seen: set[Path] = set()
    queue = [css_path.resolve()]
    while queue:
        current = queue.pop(0)
        if current in seen or not current.is_file():
            continue
        seen.add(current)
        text = current.read_text(encoding="utf-8")
        classes.update(CLASS_RE.findall(text))
        for match in re.finditer(r'@import\s+url\(["\']?([^"\')]+)["\']?\)', text):
            queue.append((current.parent / match.group(1)).resolve())
    return classes


def validate_questions_v2(json_text: str, qtypes: dict) -> list[str]:
    """Validate v2 JSON question block."""
    errors: list[str] = []
    try:
        questions = json.loads(json_text)
    except json.JSONDecodeError as exc:
        return [f"题库 JSON 解析失败：{exc}"]
    if not isinstance(questions, list):
        return ["题库必须是 JSON 数组"]
    ids: set[str] = set()
    for i, q in enumerate(questions):
        if not isinstance(q, dict):
            errors.append(f"题 {i+1} 不是对象")
            continue
        qtype = q.get("type", "single_choice")
        if qtype not in qtypes:
            errors.append(f"题 {i+1} 未知题型：{qtype}")
            continue
        spec_def = qtypes[qtype]
        required = spec_def.get("required_fields", [])
        for field in required:
            if field not in q:
                errors.append(f"题 {i+1} 缺少字段：{field}")
        qid = q.get("id")
        if not qid:
            errors.append(f"题 {i+1} 缺少 id")
        elif qid in ids:
            errors.append(f"题 {i+1} 重复 id：{qid}")
        else:
            ids.add(qid)
        if qtype == "single_choice":
            opts = q.get("options", [])
            rules = spec_def.get("rules", {})
            mn = rules.get("min_options", 2)
            mx = rules.get("max_options", 6)
            if not isinstance(opts, list) or len(opts) < mn or len(opts) > mx:
                errors.append(f"题 {i+1} 选项数需在 {mn}-{mx} 之间")
            ans = q.get("answer")
            if not isinstance(ans, int) or ans < 0 or (isinstance(opts, list) and ans >= len(opts)):
                errors.append(f"题 {i+1} answer 越界")
        elif qtype == "flashcard":
            if not q.get("answer_text"):
                errors.append(f"题 {i+1} flashcard 缺少 answer_text")
        # Check for HTML injection in text fields
        for field in ("stem", "rationale", "answer_text", "audio_text"):
            val = q.get(field, "")
            if isinstance(val, str) and ("<" in val or ">" in val):
                errors.append(f"题 {i+1} {field} 不允许 HTML")
    return errors


def validate_audio_config(json_text: str) -> list[str]:
    """Validate audio-config JSON: HTTPS only, no secrets, explicit remote permission."""
    errors: list[str] = []
    try:
        cfg = json.loads(json_text)
    except json.JSONDecodeError as exc:
        return [f"audio-config JSON 解析失败：{exc}"]
    if not isinstance(cfg, dict):
        return ["audio-config 必须是 JSON 对象"]
    for key in ("tts_endpoint", "fallback_url"):
        val = cfg.get(key, "")
        if val and not re.match(r"^https://", val):
            errors.append(f"audio-config {key} 必须 HTTPS")
    for needle in ("api_key", "apikey", "secret", "token", "password"):
        if needle.lower() in json_text.lower():
            errors.append(f"audio-config 不允许包含 {needle}")
            break
    return errors


def validate_file(page: Path, spec: dict) -> list[str]:
    errors: list[str] = []
    if not page.is_file():
        return [f"File not found: {page}"]

    text = page.read_text(encoding="utf-8")
    parser = LessonParser()
    try:
        parser.feed(text)
    except Exception as exc:
        return [f"HTML parse error: {exc}"]

    ui_version = parser.body_attrs.get("data-ui-version")
    page_format = parser.body_attrs.get("data-format")
    theme = parser.body_attrs.get("data-theme")
    pipeline = parser.body_attrs.get("data-pipeline")

    valid_formats = spec_formats(spec)
    valid_themes = spec_themes(spec)
    valid_pipelines = spec_pipelines(spec)
    qtypes = spec.get("question_types", {})

    if ui_version != "2":
        errors.append('data-ui-version must be "2"')
    if page_format not in valid_formats:
        errors.append(f"Unknown data-format: {page_format or 'missing'}")
    if theme not in valid_themes:
        errors.append(f"Unknown data-theme: {theme or 'missing'}")
    if pipeline and pipeline not in valid_pipelines:
        errors.append(f"Unknown data-pipeline: {pipeline}")

    if parser.styles:
        errors.append("<style> tags forbidden")
    if parser.inline_styles:
        errors.append("Inline style forbidden: " + ", ".join(parser.inline_styles))
    if parser.remote_resources:
        errors.append("Remote resources forbidden: " + ", ".join(parser.remote_resources))

    leftover = re.findall(r"__[A-Z][A-Z0-9_]+__", text)
    if leftover:
        errors.append("Unreplaced placeholders: " + ", ".join(sorted(set(leftover))))

    # Stylesheet check: must be exactly one, pointing to shared CSS
    expected_css = spec.get("assets", {}).get("css_entry", "../assets/lesson.css")
    expected_js = spec.get("assets", {}).get("js_entry", "../assets/lesson.js")
    if parser.stylesheets != [expected_css]:
        errors.append(f"CSS must be exactly {expected_css}")
    if parser.external_scripts != [expected_js]:
        errors.append(f"JS must be exactly {expected_js}")

    css_path = (page.parent / expected_css).resolve()
    js_path = (page.parent / expected_js).resolve()
    if not css_path.is_file():
        errors.append(f"CSS not found: {css_path}")
    if not js_path.is_file():
        errors.append(f"JS not found: {js_path}")

    if css_path.is_file():
        unknown = sorted(parser.classes - allowed_classes(css_path))
        if unknown:
            errors.append("Unknown component classes: " + ", ".join(unknown))

   # Question validation: v2 JSON preferred, v1 JS accepted during migration
    has_quiz = "quiz-section" in parser.classes
    has_production = "production-section" in parser.classes

    # Separate JSON blocks by id: lesson-questions vs audio-config
    q_json = ""
    audio_json = ""
    for sid, content in zip(parser.json_script_ids, parser.json_scripts):
        if sid == "lesson-questions":
            q_json = content
        elif sid == "audio-config":
            audio_json = content
        else:
            # Unrecognised JSON block: treat as questions if no id
            if not sid and not q_json:
                q_json = content

    if audio_json:
        errors.extend(validate_audio_config(audio_json))

    if has_quiz:
        for required_id in ("quiz", "scoreText", "resetQuiz"):
            if required_id not in parser.ids:
                errors.append(f"Quiz page missing #{required_id}")
        if q_json:
            q_errors = validate_questions_v2(q_json, qtypes)
            errors.extend(q_errors)
        elif any("LESSON_QUESTIONS" in s for s in parser.inline_scripts):
            pass  # v1 fallback during migration
        else:
            errors.append("Quiz page missing question data (JSON or LESSON_QUESTIONS)")
    else:
        if q_json:
            errors.append("Non-quiz page should not declare questions")
        if any("LESSON_QUESTIONS" in s for s in parser.inline_scripts):
            errors.append("Non-quiz page should not declare questions")

    # Production tasks need stable data-item-id
    if has_production:
        for idx, tid in enumerate(parser.production_task_ids):
            if not tid:
                errors.append(f"production-task {idx+1} missing data-item-id")
        prod_dupes = sorted({x for x in parser.production_task_ids if x and parser.production_task_ids.count(x) > 1})
        if prod_dupes:
            errors.append("Duplicate production-task data-item-id: " + ", ".join(prod_dupes))

    # Inline script check: only JSON question blocks or v1 LESSON_QUESTIONS
    for script in parser.inline_scripts:
        stripped = script.strip()
        if not V1_QUESTION_RE.match(stripped) and stripped:
            # Allow empty scripts
            if stripped:
                errors.append("Inline script must only declare questions")

    duplicates = sorted({item for item in parser.ids if parser.ids.count(item) > 1})
    if duplicates:
        errors.append("Duplicate IDs: " + ", ".join(duplicates))

    missing_fragments = sorted(set(parser.fragments) - set(parser.ids))
    if missing_fragments:
        errors.append("Broken anchors: " + ", ".join(missing_fragments))

    if parser.buttons_without_type:
        errors.append("Buttons without type: " + ", ".join(parser.buttons_without_type))

    levels = [level for level, _ in parser.headings]
    if levels.count(1) != 1:
        errors.append("Page must have exactly one h1")
    for prev, curr in zip(levels, levels[1:]):
        if curr > prev + 1:
            errors.append(f"Heading level jump: h{prev} -> h{curr}")
            break

    required = spec_required_classes(spec, page_format or "")
    missing_classes = sorted(required - parser.classes)
    if missing_classes:
        errors.append(f"{page_format} missing required classes: " + ", ".join(missing_classes))

    # External links must use rel=noopener
    for href, rel in zip(parser.external_links, parser.external_link_rels):
        if "noopener" not in rel:
            errors.append(f"External link missing rel=noopener: {href}")

    # Practice alternatives: lesson format may use quiz OR production
    fmt_def = spec.get("formats", {}).get(page_format or "", {})
    alternatives = fmt_def.get("practice_alternatives")
    if alternatives:
        satisfied = any(all(cls in parser.classes for cls in group) for group in alternatives)
        if not satisfied:
            groups = " / ".join(" + ".join(g) for g in alternatives)
            errors.append(f"{page_format} practice stage needs one of: {groups}")

    return errors


def iter_project_pages(project: Path) -> list[Path]:
    pages: list[Path] = []
    for relative in ("outputs/lessons", "outputs/reference"):
        folder = project / relative
        if folder.is_dir():
            pages.extend(sorted(folder.glob("*.html")))
    return pages


def validate_kit(script_dir: Path, spec: dict) -> list[str]:
    errors: list[str] = []
    kit_dir = script_dir / "assets" / "ui-kit"

    # Check all spec-referenced files exist
    assets = spec.get("assets", {})
    for split in assets.get("css_splits", []):
        if not (kit_dir / "assets" / split).is_file():
            errors.append(f"Missing CSS split: {split}")
    entry = kit_dir / "assets" / "lesson.css"
    if not entry.is_file():
        errors.append("Missing CSS entry: lesson.css")
    elif not (kit_dir / "assets" / "lesson.js").is_file():
        errors.append("Missing JS entry: lesson.js")
    else:
        entry_text = entry.read_text(encoding="utf-8")
        for split in assets.get("css_splits", []):
            if split not in entry_text:
                errors.append(f"lesson.css missing @import {split}")

    for name, rel in spec.get("templates", {}).items():
        # Templates are relative to project root; in kit they're in templates/
        tmpl = kit_dir / "templates" / f"{name}.html"
        if not tmpl.is_file():
            errors.append(f"Missing template: {name}")

    catalog = spec.get("component_catalog", "")
    if catalog:
        cat_name = Path(catalog).name
        if not (kit_dir / "templates" / cat_name).is_file():
            errors.append(f"Missing component catalog: {cat_name}")

    # Validate that spec formats/themes match
    fmts = spec_formats(spec)
    if not fmts:
        errors.append("No formats defined in spec")
    themes = spec_themes(spec)
    if len(themes) < 3:
        errors.append("Too few themes in spec")

    # Validate templates themselves
    for tmpl in sorted((kit_dir / "templates").glob("*.html")):
        tmpl_errors = validate_file(tmpl, spec)
        # Templates have placeholders, so skip placeholder errors
        real_errors = [e for e in tmpl_errors if "placeholder" not in e.lower()]
        if real_errors:
            errors.append(f"Template {tmpl.name}: {'; '.join(real_errors)}")

    return errors


def run_self_test(script_dir: Path, spec: dict) -> list[str]:
    failures: list[str] = []
    kit_assets = script_dir / "assets" / "ui-kit" / "assets"
    with tempfile.TemporaryDirectory(prefix="fyuu-ui-test-") as temp:
        root = Path(temp)
        assets_dir = root / "assets"
        assets_dir.mkdir()
        ref_dir = root / "reference"
        ref_dir.mkdir()
        for f in sorted(kit_assets.glob("*")):
            shutil.copy2(f, assets_dir / f.name)

        valid = (
            '<!doctype html><html lang="en"><head>'
            '<link rel="stylesheet" href="../assets/lesson.css"></head>'
            '<body data-ui-version="2" data-pipeline="capability" data-format="reference" data-theme="overview">'
            '<main class="lesson-shell" id="main"><header class="lesson-header"><h1>Test</h1></header>'
            '<section class="reference-section"><h2>Content</h2></section>'
            '<footer class="lesson-footer"><p>Done</p></footer></main>'
            '<script src="../assets/lesson.js"></script></body></html>'
        )
        cases = {
            "valid": (valid, False),
            "inline-style": (valid.replace("<h1>", '<h1 style="color:red">'), True),
            "unknown-theme": (valid.replace('data-theme="overview"', 'data-theme="neon"'), True),
            "unknown-format": (valid.replace('data-format="reference"', 'data-format="deck"'), True),
            "v1-version": (valid.replace('data-ui-version="2"', 'data-ui-version="1"'), True),
            "remote": (valid.replace("</head>", '<link rel="preload" href="https://x.test/a"></head>'), True),
            "duplicate-id": (valid.replace("<h2>", '<h2 id="main">'), True),
            "unknown-class": (valid.replace('class="reference-section"', 'class="reference-section rogue-card"'), True),
            "missing-asset": (valid.replace("../assets/lesson.css", "../assets/missing.css"), True),
        }
        for name, (html, should_fail) in cases.items():
            page = ref_dir / f"{name}.html"
            page.write_text(html, encoding="utf-8")
            errors = validate_file(page, spec)
            if should_fail != bool(errors):
                failures.append(f"{name}: {'unexpected pass' if should_fail else errors}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--file", type=Path)
    target.add_argument("--project", type=Path)
    target.add_argument("--kit", action="store_true")
    target.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent.parent
    spec = load_spec(script_dir)

    if args.kit:
        errors = validate_kit(script_dir, spec)
        if errors:
            print("FAIL kit")
            print("\n".join(f"  - {e}" for e in errors))
            return 1
        print("OK kit: spec, templates, components, CSS, JS all consistent")
        return 0

    if args.self_test:
        failures = run_self_test(script_dir, spec)
        if failures:
            print("FAIL self-test")
            print("\n".join(f"- {item}" for item in failures))
            return 1
        print("OK self-test: 1 valid + 8 rejection cases passed")
        return 0

    if args.file:
        pages = [args.file.resolve()]
    else:
        project = args.project.resolve()
        pages = iter_project_pages(project)
        if not pages:
            print(f"FAIL: no HTML found in {project}", file=sys.stderr)
            return 1

    failed = False
    for page in pages:
        errors = validate_file(page, spec)
        if errors:
            failed = True
            print(f"FAIL {page}")
            print("\n".join(f"  - {error}" for error in errors))
        else:
            print(f"OK {page}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
