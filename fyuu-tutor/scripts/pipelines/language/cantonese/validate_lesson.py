#!/usr/bin/env python3
"""Validate one configured language lesson."""

import argparse
from html.parser import HTMLParser
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from project_config import load_project, resolve_child, resolve_path


class TagBalanceParser(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__()
        self.stack, self.errors = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(tag)
        else:
            self.stack.pop()


def lesson_path(lessons, lesson):
    try:
        direct = resolve_child(lessons, lesson, "--lesson")
    except ValueError as exc:
        raise SystemExit(exc)
    if direct.is_file():
        return direct
    matches = list(lessons.glob(f"{lesson}-*.html"))
    if len(matches) != 1:
        raise SystemExit(f"expected one lesson for {lesson}, found {len(matches)}")
    return matches[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--lesson", required=True)
    args = parser.parse_args()
    root, config, pipeline = load_project(args.project)
    path = lesson_path(resolve_path(root, config, "lessons"), args.lesson)
    lesson_id = re.search(r"\d{4}", path.name).group(0)
    targets = pipeline.get("lessons", {}).get(lesson_id, {}).get("target_words", [])
    if not targets:
        raise SystemExit(f"no target_words configured for lesson {lesson_id}")
    html = path.read_text(encoding="utf-8")
    positions = [html.find(marker) for marker in ('<span class="tag practice">', "課後練習", "课后练习")]
    positions = [position for position in positions if position >= 0]
    practice = html[min(positions):] if positions else ""
    covered = [target for target in targets if target in practice]
    target_ratio = len(covered) / len(targets)
    fill_questions = len(re.findall(r'class="fill-q"[^>]*>', practice))
    reveals = len(re.findall(r'class="btn-reveal"[^>]*>', practice))
    scenarios = len(re.findall(r'class="scenario"[^>]*>', practice))
    flashcards = len(re.findall(r'class="[^"]*flash(?:card)?[^"]*"', practice, re.I))
    outputs = fill_questions + reveals + scenarios
    total = outputs + flashcards
    output_ratio = outputs / total if total else 0
    parser_check = TagBalanceParser()
    parser_check.feed(html)
    spk = html.count('class="spk"')
    data_canto = html.count("data-canto") - html.count("getAttribute('data-canto')")
    checks = {
        "vocabulary": len(re.findall(r'class="v-item"[^>]*>', html)) >= 6,
        "oral_output": html.count("btn-prac") >= len(re.findall(r'class="s-card"[^>]*>', html)) >= 4,
        "source_exercises": all(term in html for term in ("讀音跟讀", "句子翻譯", "情景填空")),
        "scene": ("教材場景" in html or "教材场景" in html) and ("場景應變" in html or "应变" in html),
        "target_coverage": bool(positions) and target_ratio >= 0.8,
        "output_ratio": outputs >= 4 and output_ratio >= 0.8,
        "target_presence": all(target in html for target in targets),
        "technical": not parser_check.errors and not parser_check.stack and spk == data_canto and "function speak" in html and "zh-HK" in html,
    }
    for name, passed in checks.items():
        print(f"{'PASS' if passed else 'FAIL'} {name}")
    print(f"target coverage {len(covered)}/{len(targets)}={target_ratio:.0%}; output ratio {outputs}/{total}={output_ratio:.0%}")
    raise SystemExit(0 if all(checks.values()) else 1)


if __name__ == "__main__":
    main()
