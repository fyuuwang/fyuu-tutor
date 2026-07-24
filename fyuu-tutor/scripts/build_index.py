#!/usr/bin/env python3
"""Build one project's HTML home and refresh the private workspace shelf."""

import argparse
from html import escape
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


def page(title_text, body, language, recommended_label):
    return f'''<!doctype html>
<html lang="{escape(language)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title_text)}</title>
<style>
:root{{--bg:#f5f1e8;--card:#fffdf8;--ink:#27231f;--muted:#746c62;--accent:#aa4a2a;--line:#ded5c8}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,-apple-system,sans-serif}}
main{{max-width:920px;margin:auto;padding:42px 20px 80px}}h1{{margin:0 0 8px;font-size:clamp(30px,6vw,52px)}}h2{{margin-top:34px}}
.muted{{color:var(--muted)}}.status,.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}}.card{{display:block;color:inherit;text-decoration:none}}
.card:hover{{border-color:var(--accent);transform:translateY(-1px)}}.tag{{display:inline-block;margin-top:8px;color:var(--accent);font-size:13px}}
.recommended{{border:2px solid var(--accent)}}.recommended:before{{content:'{escape(recommended_label)}';display:block;color:var(--accent);font-size:13px;font-weight:700}}
dt{{font-weight:700}}dd{{margin:0 0 8px}}a{{color:var(--accent)}}
</style>
</head>
<body><main>{body}</main></body>
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

    body = f'''
<p><a href="../../../index.html">← {labels['back']}</a></p>
<h1>{escape(config['display_name'])}</h1><p class="muted">{escape(config['pipeline'])}</p>
<section class="status"><dl>
<dt>{labels['production']}</dt><dd>{escape(status_value(status, 'Production progress', labels['missing']))}</dd>
<dt>{labels['learning']}</dt><dd>{escape(status_value(status, 'Learning progress', labels['missing']))}</dd>
<dt>{labels['next']}</dt><dd>{escape(next_step)}</dd>
</dl></section>
<h2>{labels['lessons']}</h2>{cards(lessons)}
<h2>{labels['reviews']}</h2>{cards(reviews)}
<h2>{labels['reference']}</h2>{cards(references)}
'''
    outputs.mkdir(parents=True, exist_ok=True)
    (outputs / "index.html").write_text(page(f"{config['display_name']} · {labels['entry']}", body, language, labels["recommended"]), encoding="utf-8")


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
