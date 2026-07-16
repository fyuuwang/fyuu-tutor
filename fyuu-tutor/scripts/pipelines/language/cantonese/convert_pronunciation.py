#!/usr/bin/env python3
"""Create a Jyutping table using private authority overrides from pipeline.toml."""

import argparse
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from project_config import load_project, resolve_child, resolve_path


def extract_vocab(text):
    words = re.findall(r"^- ([^（(]+?)\s*[（(]", text, re.MULTILINE)
    return list(dict.fromkeys(word.strip() for word in words if word.strip()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root, config, pipeline = load_project(args.project)
    sources = resolve_path(root, config, "sources")
    authority = pipeline.get("language", {}).get("authority", {})
    from pycantonese import characters_to_jyutping
    try:
        source = resolve_child(sources, args.source, "--source")
        output = resolve_child(sources, args.output, "--output")
    except ValueError as exc:
        raise SystemExit(exc)
    words = extract_vocab(source.read_text(encoding="utf-8"))
    rows = []
    for word in words:
        if word in authority:
            pronunciation, confidence = authority[word], "权威锁定"
        else:
            try:
                result = characters_to_jyutping(word)
                pronunciation = " ".join(value or "?" for _, value in result)
                confidence = "库转-待抽验"
            except Exception:
                pronunciation, confidence = "?", "转换失败"
        rows.append(f"| {word} | {pronunciation} | {confidence} |")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("# 粤拼对照表\n\n| 词汇 | Jyutping | 置信度 |\n|---|---|---|\n" + "\n".join(rows) + "\n", encoding="utf-8")
    print(f"OK {len(rows)} words -> {output}")


if __name__ == "__main__":
    main()
