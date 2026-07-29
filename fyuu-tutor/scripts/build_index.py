#!/usr/bin/env python3
"""Build one project's HTML home and refresh the private workspace shelf."""

import argparse
from html import escape
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_config import load_project, resolve_path, status_value


UI = {
    "en": {
        "missing": "Not recorded", "recommended": "Recommended now", "back": "Back to learning shelf",
        "production": "Production progress", "learning": "Learning progress", "next": "Next action",
        "lessons": "Lessons", "reviews": "Reviews", "reference": "Reference", "empty": "No content yet.",
        "entry": "Course index", "shelf": "Learning shelf", "shelf_intro": "Choose a project to open its course. STATUS.md remains the source of truth.",
    },
    "zh-CN": {
        "missing": "未记录", "recommended": "当前建议", "back": "返回学习书架",
        "production": "内容生产进度", "learning": "用户学习进度", "next": "下一步",
        "lessons": "课程", "reviews": "复习课", "reference": "参考资料", "empty": "暂无内容。",
        "entry": "课程入口", "shelf": "学习书架", "shelf_intro": "选择项目后进入课程。学习进度仍以各项目 STATUS.md 为准。",
    },
}


def ui(language):
    return UI["zh-CN"] if str(language).lower().startswith("zh") else UI["en"]


def title(path):
    text = path.read_text(encoding="utf-8")
    match = re.search(r"<title>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else path.stem


def lesson_key(path):
    match = re.match(r"(\d{4})([a-z]?)", path.stem, re.IGNORECASE)
    return (int(match.group(1)), match.group(2).lower(), path.name) if match else (9999, "", path.name)


def recommended_entry(next_step, entries):
    wanted = re.findall(r"(?<!\d)(\d{4}[a-z]?)(?!\w)", next_step, re.IGNORECASE)
    if len(wanted) != 1:
        return None
    code = wanted[0].lower()
    return next((path for path in entries if path.stem.lower().startswith(code + "-")), None)


def href(from_dir, target):
    return quote(str(target.relative_to(from_dir)).replace("\\", "/"), safe="/")


def page(title_text, body, language, recommended_label, portal_href=None):
    return f'''<!doctype html>
<html lang="{escape(language)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title_text)}</title>
<style>
:root{{--bg:#eff1f3;--card:#fff;--ink:#202634;--muted:#5f6673;--accent:#84765f;--soft:#f4f1eb;--line:#d9dce2}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,-apple-system,sans-serif}}
main{{max-width:1080px;margin:32px auto 64px;padding:clamp(24px,5vw,48px);background:var(--card);border:1px solid var(--line);border-radius:18px;box-shadow:0 18px 48px rgba(23,32,51,.08)}}h1{{margin:0 0 8px;font-size:clamp(30px,6vw,46px)}}h2{{margin-top:34px}}
.muted{{color:var(--muted)}}.status,.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px}}.status{{background:var(--soft)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}}.card{{display:block;color:inherit;text-decoration:none;border-left:3px solid var(--accent)}}
.card:hover{{border-color:var(--accent);transform:translateY(-1px)}}.tag{{display:inline-block;margin-top:8px;color:var(--accent);font-size:13px}}
.recommended{{border:2px solid var(--accent)}}.recommended:before{{content:'{escape(recommended_label)}';display:block;color:var(--accent);font-size:13px;font-weight:700}}.course-return-dock{{position:fixed;right:max(16px,env(safe-area-inset-right));bottom:max(16px,env(safe-area-inset-bottom));z-index:15;overflow:hidden;border:1px solid var(--line);border-radius:999px;background:rgba(255,255,255,.96);box-shadow:0 12px 32px rgba(23,32,51,.14)}}.course-return-dock a{{display:inline-flex;align-items:center;justify-content:center;min-width:48px;min-height:48px;padding:10px;color:var(--muted);font-size:20px;text-decoration:none}}.course-return-dock a:hover,.course-return-dock a:focus-visible{{background:var(--soft);color:var(--accent)}}.course-return-label{{position:absolute;width:1px;height:1px;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap}}
dt{{font-weight:700}}dd{{margin:0 0 8px}}a{{color:var(--accent)}}.package{{grid-column:1/-1;margin:16px 0;padding:16px;border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:12px;background:var(--card)}}.package-head{{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap;margin-bottom:12px}}.package-number{{color:var(--accent);font-weight:700}}.package-meta{{color:var(--muted);font-size:13px}}@media(max-width:520px){{main{{margin:16px auto 40px;padding:24px 18px}}}}
</style>
</head>
<body><main>{body}</main>{f'<nav class="course-return-dock" aria-label="Global learning navigation"><a href="{escape(portal_href)}" aria-label="{escape(UI["zh-CN"]["back"] if str(language).lower().startswith("zh") else UI["en"]["back"])}" title="{escape(UI["zh-CN"]["shelf"] if str(language).lower().startswith("zh") else UI["en"]["shelf"])}"><span aria-hidden="true">⌂</span><span class="course-return-label">{escape(UI["zh-CN"]["shelf"] if str(language).lower().startswith("zh") else UI["en"]["shelf"])}</span></a></nav>' if portal_href else ''}</body>
</html>
'''


def build_project(root, config):
    language = config.get("content_language", "en")
    labels = ui(language)
    outputs = root / "outputs"
    lessons_dir = resolve_path(root, config, "lessons")
    reference_dir = resolve_path(root, config, "reference")
    status = (root / "STATUS.md").read_text(encoding="utf-8")
    next_step = status_value(status, "Next action", labels["missing"])
    entries = [p for p in lessons_dir.glob("*.html") if p.name != "index.html"]
    lessons = sorted((p for p in entries if "review" not in p.stem.lower()), key=lesson_key)
    reviews = sorted((p for p in entries if "review" in p.stem.lower()), key=lesson_key)
    references = sorted((p for p in reference_dir.rglob("*.html")), key=lambda p: p.name)
    recommended = recommended_entry(next_step, entries)

    def cards(paths):
        items = []
        for path in paths:
            css = "card recommended" if path == recommended else "card"
            items.append(f'<a class="{css}" href="{href(outputs, path)}"><strong>{escape(title(path))}</strong><span class="tag">{escape(path.stem)}</span></a>')
        return '<div class="grid">' + "".join(items) + "</div>" if items else f'<p class="muted">{labels["empty"]}</p>'

    def lesson_cards(paths):
        manifest = outputs / "catalog.json"
        try:
            catalog = json.loads(manifest.read_text(encoding="utf-8")) if manifest.is_file() else {"groups": []}
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            catalog = {"groups": []}
        by_name = {path.name: path for path in paths}
        grouped = set()
        blocks = []
        for group in catalog.get("groups", []):
            if not isinstance(group, dict):
                continue
            children = []
            for part in group.get("parts", []):
                if not isinstance(part, dict):
                    continue
                path = by_name.get(part.get("href"))
                if path:
                    grouped.add(path)
                    css = "card recommended" if path == recommended else "card"
                    part_id = str(part.get("id", path.stem))
                    label = part_id[2:] if len(part_id) == 5 and part_id[:4].isdigit() else part_id
                    children.append(f'<a class="{css}" href="{href(outputs, path)}"><strong>{escape(label)} · {escape(part.get("title", title(path)))}</strong></a>')
            if children:
                order = lesson_key(Path(group.get("id", "9999") + ".html"))
                blocks.append((order, f'<section class="package"><div class="package-head"><span class="package-number">第 {int(group["id"]):02d} 课</span><strong>{escape(group.get("title", "课程包"))}</strong><span class="package-meta">{len(children)}/{len(group.get("parts", []))} 个微课已产出</span></div><div class="grid">{"".join(children)}</div></section>'))
        for path in paths:
            if path not in grouped:
                css = "card recommended" if path == recommended else "card"
                blocks.append((lesson_key(path), f'<a class="{css}" href="{href(outputs, path)}"><strong>{escape(title(path))}</strong><span class="tag">{escape(path.stem)}</span></a>'))
        rendered = "".join(html for _, html in sorted(blocks, key=lambda item: item[0]))
        return f'<div class="grid">{rendered}</div>' if rendered else f'<p class="muted">{labels["empty"]}</p>'

    body = f'''
<h1>{escape(config['display_name'])}</h1><p class="muted">{escape(config['pipeline'])}</p>
<section class="status"><dl>
<dt>{labels['production']}</dt><dd>{escape(status_value(status, 'Production progress', labels['missing']))}</dd>
<dt>{labels['learning']}</dt><dd>{escape(status_value(status, 'Learning progress', labels['missing']))}</dd>
<dt>{labels['next']}</dt><dd>{escape(next_step)}</dd>
</dl></section>
<h2>{labels['lessons']}</h2>{lesson_cards(lessons)}
{f"<h2>{labels['reviews']}</h2>{cards(reviews)}" if reviews else ''}
{f"<h2>{labels['reference']}</h2>{cards(references)}" if references else ''}
'''
    outputs.mkdir(parents=True, exist_ok=True)
    (outputs / "index.html").write_text(page(f"{config['display_name']} · {labels['entry']}", body, language, labels["recommended"], "../../../index.html"), encoding="utf-8")


def build_workspace(projects_root):
    workspace = projects_root.parent
    cards = []
    projects = []
    for root in sorted((p for p in projects_root.iterdir() if (p / "project.toml").is_file()), key=lambda p: p.name):
        _, config, _ = load_project(root)
        projects.append((root, config))
    language = "zh-CN" if projects and all(str(config.get("content_language", "")).lower().startswith("zh") for _, config in projects) else "en"
    labels = ui(language)
    for root, config in projects:
        status = (root / "STATUS.md").read_text(encoding="utf-8")
        target = root / "outputs" / "index.html"
        if not target.is_file():
            continue
        cards.append(f'''
<a class="card" href="{href(workspace, target)}">
<strong>{escape(config['display_name'])}</strong><span class="tag">{escape(config['pipeline'])}</span>
<p>{escape(status_value(status, 'Production progress', labels['missing']))}</p>
<p class="muted">{labels['next']}: {escape(status_value(status, 'Next action', labels['missing']))}</p>
</a>''')
    body = f'''<h1>{labels['shelf']}</h1><p class="muted">{labels['shelf_intro']}</p><div class="grid">{"".join(cards)}</div>'''
    (workspace / "index.html").write_text(page(labels["shelf"], body, language, labels["recommended"]), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    root, config, _ = load_project(args.project)
    build_project(root, config)
    build_workspace(root.parent)
    print(f"OK indexes: {root / 'outputs/index.html'} and {root.parent.parent / 'index.html'}")


if __name__ == "__main__":
    main()
