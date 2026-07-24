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
        self.components: list[tuple[str, set[str]]] = []
        self.stages: list[str] = []
        self.section_stages: list[str] = []
        self.section_stage_ids: list[tuple[str, str]] = []
        self._current_section_stage: str = ""
        self.section_index_links: list[str] = []
        self.stage_item_counts: dict[str, int] = {}
        self.duplicate_attributes: list[str] = []
        self._element_stack: list[tuple[str, set[str]]] = []
        self._script_id: str = ""

    def handle_starttag(self, tag, attrs_list):
        seen_attrs = set()
        for name, _ in attrs_list:
            if name in seen_attrs:
                self.duplicate_attributes.append(f"{tag}[{name}]")
            seen_attrs.add(name)
        attrs = {k: v or "" for k, v in attrs_list}
        own_classes = set(attrs.get("class", "").split())
        if tag == "body":
            self.body_attrs = attrs
        if tag == "style":
            self.styles += 1
        if "style" in attrs:
            self.inline_styles.append(tag)
        if own_classes:
            self.classes.update(own_classes)
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
        if attrs.get("data-component"):
            parent_classes = set().union(*(classes for _, classes in self._element_stack)) if self._element_stack else set()
            self.components.append((attrs["data-component"], parent_classes | own_classes))
        if attrs.get("data-stage"):
            self.stages.append(attrs["data-stage"])
        if own_classes and "section-index-link" in own_classes:
            self.section_index_links.append(attrs.get("href", ""))
        if tag == "section" and attrs.get("data-stage"):
            self._current_section_stage = attrs["data-stage"]
            self.section_stages.append(self._current_section_stage)
            self.section_stage_ids.append((self._current_section_stage, attrs.get("id", "")))
            if self._current_section_stage not in self.stage_item_counts:
                self.stage_item_counts[self._current_section_stage] = 0
        if own_classes and "reference-item" in own_classes and self._current_section_stage:
            self.stage_item_counts[self._current_section_stage] = self.stage_item_counts.get(self._current_section_stage, 0) + 1
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
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}:
            self._element_stack.append((tag, own_classes))

    def handle_endtag(self, tag):
        if tag == "section":
            self._current_section_stage = ""
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
        for index in range(len(self._element_stack) - 1, -1, -1):
            if self._element_stack[index][0] == tag:
                del self._element_stack[index:]
                break

    def handle_data(self, data):
        if self._script_parts is not None:
            self._script_parts.append(data)


def allowed_classes(css_path: Path) -> set[str]:
    return set(CLASS_RE.findall(css_path.read_text(encoding="utf-8")))


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
        allowed = set(required) | set(spec_def.get("optional_fields", [])) | {"type"}
        unknown_fields = sorted(set(q) - allowed)
        if unknown_fields:
            errors.append(f"题 {i+1} 含有未知字段：{', '.join(unknown_fields)}")
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
            if field in q and not isinstance(val, str):
                errors.append(f"题 {i+1} {field} 必须为纯文本")
            elif isinstance(val, str) and ("<" in val or ">" in val):
                errors.append(f"题 {i+1} {field} 不允许 HTML")
        for option in q.get("options", []):
            if not isinstance(option, str) or "<" in option or ">" in option:
                errors.append(f"题 {i+1} options 不允许 HTML 且必须为纯文本")
                break
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
    if cfg.get("tts_endpoint") and cfg.get("allow_remote_tts") is not True:
        errors.append("audio-config tts_endpoint requires allow_remote_tts: true")
    if cfg.get("allow_remote_tts") is True and not cfg.get("tts_endpoint"):
        errors.append("audio-config allow_remote_tts requires tts_endpoint")
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
    if pipeline not in valid_pipelines:
        errors.append(f"Unknown data-pipeline: {pipeline or 'missing'}")
    if parser.duplicate_attributes:
        errors.append("Duplicate HTML attributes: " + ", ".join(parser.duplicate_attributes))

    if page_format == "lesson":
        expected_stages = spec.get("formats", {}).get("lesson", {}).get("stages", [])
        stage_order = list(dict.fromkeys(parser.stages))
        if stage_order != expected_stages:
            errors.append("lesson data-stage order must be: " + ", ".join(expected_stages))

    # scene must not appear in reference pages; use chapter-header instead
    if page_format == "reference" and "scene" in parser.classes:
        errors.append("scene component is forbidden in reference format; use chapter-header for section grouping")

    if page_format == "reference":
        links = parser.section_index_links
        if links and not 2 <= len(links) <= 3:
            errors.append(f"section-index must have 2-3 tabs, found {len(links)}")
        if not links and parser.section_stages:
            errors.append("reference data-stage requires a section-index")
        if links:
            invalid = [href for href in links if not re.fullmatch(r"#[A-Za-z0-9][A-Za-z0-9_-]*", href)]
            if invalid:
                errors.append("Invalid section-index targets: " + ", ".join(invalid))
            targets = [href[1:] for href in links if href.startswith("#") and len(href) > 1]
            nav_targets = set(targets)
            section_stages = set(parser.section_stages)
            if len(nav_targets) != len(targets):
                errors.append("Duplicate section-index targets")
            missing_groups = nav_targets - section_stages
            if missing_groups:
                errors.append("section-index target has no data-stage group: " + ", ".join(sorted(missing_groups)))
            orphaned_groups = section_stages - nav_targets
            if orphaned_groups:
                errors.append("data-stage group has no section-index target: " + ", ".join(sorted(orphaned_groups)))
            missing_ids = nav_targets - set(parser.ids)
            if missing_ids:
                errors.append("section-index target has no matching id: " + ", ".join(sorted(missing_ids)))
            detached_targets = sorted(target for target in nav_targets if (target, target) not in parser.section_stage_ids)
            if detached_targets:
                errors.append("section-index target id and data-stage must share one section: " + ", ".join(detached_targets))
            empty_groups = sorted(target for target in nav_targets if parser.stage_item_counts.get(target, 0) == 0)
            if empty_groups:
                errors.append("section-index target maps to an empty chapter (no reference items): " + ", ".join(empty_groups))

    # content imbalance: max tab should not exceed 3x min tab
    if page_format == "reference" and parser.section_index_links and parser.stage_item_counts:
        counts = [v for v in parser.stage_item_counts.values() if v > 0]
        if len(counts) >= 2:
            mx = max(counts)
            mn = min(counts)
            if mx > mn * 3:
                mx_stage = [k for k, v in parser.stage_item_counts.items() if v == mx][0]
                mn_stage = [k for k, v in parser.stage_item_counts.items() if v == mn][0]
                errors.append(f"content imbalance: tab '{mx_stage}' has {mx} items, tab '{mn_stage}' has {mn} items (max exceeds 3x min)")

    for component, parent_classes in parser.components:
        definition = spec_components(spec).get(component)
        if not definition:
            errors.append(f"Unknown data-component: {component}")
            continue
        allowed_pipelines = set(definition.get("pipelines", []))
        if pipeline and pipeline not in allowed_pipelines:
            errors.append(f"{component} is not allowed for pipeline {pipeline}")
        allowed_sections = set(definition.get("sections", []))
        if "root" not in allowed_sections and not (allowed_sections & parent_classes):
            errors.append(f"{component} is outside its allowed section")

    if parser.styles:
        errors.append("<style> tags forbidden")
    if parser.inline_styles:
        errors.append("Inline style forbidden: " + ", ".join(parser.inline_styles))
    if parser.remote_resources:
        errors.append("Remote resources forbidden: " + ", ".join(parser.remote_resources))

    leftover = re.findall(r"__[A-Z][A-Z0-9_]+__", text)
    if leftover:
        errors.append("Unreplaced placeholders: " + ", ".join(sorted(set(leftover))))

    # Writing-guide brackets like [Scene title] are human hints, not tokens;
    # shipping them unfilled means a template skeleton was published as content.
    # Match a bracket that starts with a letter and contains a space (template
    # guides) while skipping attribute selectors [hidden]/[data-theme="x"] and
    # JS array access [index].
    guide_leftover = re.findall(r"\[[A-Za-z][^\]\n]* [^\]\n]*\]", text)
    if guide_leftover:
        errors.append("Unreplaced writing-guide placeholders: " + ", ".join(sorted(set(guide_leftover))))

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

    # Question validation: strict JSON only.
    has_quiz = "quiz-section" in parser.classes

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
        else:
            errors.append("Quiz page missing JSON question data")
    else:
        if q_json:
            errors.append("Non-quiz page should not declare questions")

    # Production tasks need stable data-item-id wherever they appear.
    for idx, tid in enumerate(parser.production_task_ids):
        if not tid:
            errors.append(f"production-task {idx+1} missing data-item-id")
    prod_dupes = sorted({x for x in parser.production_task_ids if x and parser.production_task_ids.count(x) > 1})
    if prod_dupes:
        errors.append("Duplicate production-task data-item-id: " + ", ".join(prod_dupes))

    # Inline script check: question and audio data must be strict JSON.
    for script in parser.inline_scripts:
        if script.strip():
            errors.append("Inline script forbidden; use a JSON data block")

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
        # Verify lesson.css is the concatenation of the three CSS sources
        kit_assets = kit_dir / "assets"
        from sync_ui_kit import build_lesson_css
        expected = build_lesson_css(kit_assets)
        actual = entry.read_text(encoding="utf-8")
        if expected != actual:
            errors.append("lesson.css is out of sync with tokens + foundation + components; run sync_ui_kit.py --build-css")

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

    gallery = spec.get("gallery", "")
    if gallery:
        gallery_name = Path(gallery).name
        if not (kit_dir / "templates" / gallery_name).is_file():
            errors.append(f"Missing gallery: {gallery_name}")

    if not (script_dir / "references" / "ui-contract.md").is_file():
        errors.append("Missing UI contract")

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
            "missing-pipeline": (valid.replace(' data-pipeline="capability"', ""), True),
            "v1-version": (valid.replace('data-ui-version="2"', 'data-ui-version="1"'), True),
            "remote": (valid.replace("</head>", '<link rel="preload" href="https://x.test/a"></head>'), True),
            "duplicate-id": (valid.replace("<h2>", '<h2 id="main">'), True),
            "unknown-class": (valid.replace('class="reference-section"', 'class="reference-section rogue-card"'), True),
            "bracket-leftover": (valid.replace("<h2>Content</h2>", "<h2>[Central concept]</h2>"), True),
            "missing-asset": (valid.replace("../assets/lesson.css", "../assets/missing.css"), True),
        }

        # Section-index test cases
        valid_index = (
            '<!doctype html><html lang="en"><head>'
            '<link rel="stylesheet" href="../assets/lesson.css"></head>'
            '<body data-ui-version="2" data-pipeline="capability" data-format="reference" data-theme="overview">'
            '<main class="lesson-shell" id="main">'
            '<nav class="section-index"><a href="#a" class="section-index-link">A</a>'
            '<a href="#b" class="section-index-link">B</a></nav>'
            '<header class="lesson-header"><h1>Test</h1></header>'
            '<section class="reference-section" id="a" data-stage="a" data-theme="overview"><h2>A</h2>'
            '<article class="reference-item"><h3>x</h3><p>y</p></article>'
            '<article class="reference-item"><h3>x</h3><p>y</p></article>'
            '</section>'
            '<section class="reference-section" id="b" data-stage="b" data-theme="overview"><h2>B</h2>'
            '<article class="reference-item"><h3>x</h3><p>y</p></article>'
            '<article class="reference-item"><h3>x</h3><p>y</p></article>'
            '</section>'
            '<footer class="lesson-footer"><p>Done</p></footer></main>'
            '<script src="../assets/lesson.js"></script></body></html>'
        )
        section_cases = {
            "valid-index": (valid_index, False),
            "too-many-tabs": (
                valid_index.replace(
                    '<a href="#b" class="section-index-link">B</a></nav>',
                    '<a href="#b" class="section-index-link">B</a>'
                    '<a href="#c" class="section-index-link">C</a>'
                    '<a href="#d" class="section-index-link">D</a></nav>'
                ), True),
            "orphan-stage": (
                valid_index.replace('data-stage="b"', 'data-stage="z"'), True),
            "content-imbalance": (
                valid_index.replace(
                    '<section class="reference-section" id="b" data-stage="b" data-theme="overview"><h2>B</h2>'
                    '<article class="reference-item"><h3>x</h3><p>y</p></article>'
                    '<article class="reference-item"><h3>x</h3><p>y</p></article>',
                    '<section class="reference-section" id="b" data-stage="b" data-theme="overview"><h2>B</h2>'
                    + '<article class="reference-item"><h3>x</h3><p>y</p></article>' * 10
                ), True),
            "missing-target-id": (valid_index.replace(' id="b"', ""), True),
            "detached-target-id": (
                valid_index.replace(
                    '<section class="reference-section" id="b" data-stage="b" data-theme="overview"><h2>B</h2>',
                    '<section class="reference-section" id="x" data-stage="b" data-theme="overview"><h2 id="b">B</h2>',
                ), True),
            "duplicate-attribute": (valid_index.replace('id="a"', 'id="a" id="duplicate"', 1), True),
            "duplicate-target": (valid_index.replace('href="#b"', 'href="#a"'), True),
            "single-tab": (valid_index.replace('<a href="#b" class="section-index-link">B</a>', ""), True),
            "stage-without-index": (
                valid_index.replace(
                    '<nav class="section-index"><a href="#a" class="section-index-link">A</a>'
                    '<a href="#b" class="section-index-link">B</a></nav>',
                    "",
                ), True),
            "invalid-target": (valid_index.replace('href="#b"', 'href="#b:bad"'), True),
            "empty-group": (
                valid_index.replace(
                    '<section class="reference-section" id="b" data-stage="b" data-theme="overview"><h2>B</h2>'
                    '<article class="reference-item"><h3>x</h3><p>y</p></article>'
                    '<article class="reference-item"><h3>x</h3><p>y</p></article>',
                    '<section class="reference-section" id="b" data-stage="b" data-theme="overview"><h2>B</h2>',
                ), True),
        }
        cases.update(section_cases)
        for name, (html, should_fail) in cases.items():
            page = ref_dir / f"{name}.html"
            page.write_text(html, encoding="utf-8")
            errors = validate_file(page, spec)
            if should_fail != bool(errors):
                failures.append(f"{name}: {'unexpected pass' if should_fail else errors}")
        if not validate_audio_config('{"tts_endpoint":"https://tts.example/"}'):
            failures.append("remote TTS without explicit consent unexpectedly passed")
        invalid_question = '[{"id":"q1","type":"single_choice","stem":"x","options":["<b>x</b>","y"],"answer":0,"rationale":"x"}]'
        if not validate_questions_v2(invalid_question, spec.get("question_types", {})):
            failures.append("HTML in option unexpectedly passed")
    if not failures:
        n_valid = sum(1 for _, should_fail in cases.values() if not should_fail)
        print(f"OK self-test: {n_valid} valid + {len(cases) - n_valid} rejection cases passed")
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
