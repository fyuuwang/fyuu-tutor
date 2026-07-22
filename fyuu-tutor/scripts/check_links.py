#!/usr/bin/env python3
"""Check local Markdown and HTML links under a project or workspace tree."""

import argparse
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
SKIP_SCHEMES = {"http", "https", "mailto", "data", "javascript"}


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in {"href", "src"} and value:
                self.values.append(value)


def local_target(source, raw):
    raw = raw.strip().strip("<>")
    if not raw or raw.startswith("#"):
        return None
    parsed = urlsplit(raw)
    if parsed.scheme.lower() in SKIP_SCHEMES or parsed.netloc:
        return None
    path = unquote(parsed.path)
    if not path:
        return None
    target = Path(path)
    return target if target.is_absolute() else source.parent / target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    errors = []
    checked = 0

    for source in sorted(root.rglob("*")):
        if "history" in source.relative_to(root).parts:
            continue
        if not source.is_file() or source.suffix.lower() not in {".md", ".html"}:
            continue
        text = source.read_text(encoding="utf-8")
        if source.suffix.lower() == ".md":
            values = MARKDOWN_LINK.findall(text)
        else:
            parser_html = Links()
            parser_html.feed(text)
            values = parser_html.values
        for raw in values:
            target = local_target(source, raw)
            if target is None:
                continue
            checked += 1
            if not target.exists():
                errors.append(f"{source.relative_to(root)} -> {raw}")

    if errors:
        for error in errors:
            print(f"ERROR broken local link: {error}")
        raise SystemExit(1)
    print(f"OK local links: {checked} checked under {root}")


if __name__ == "__main__":
    main()
