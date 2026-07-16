#!/usr/bin/env python3
"""Diagnose text layers for project source PDFs."""

import argparse
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from project_config import load_project, resolve_child, resolve_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--source", action="append", required=True)
    args = parser.parse_args()
    root, config, _ = load_project(args.project)
    sources = resolve_path(root, config, "sources")
    import fitz
    for value in args.source:
        try:
            path = resolve_child(sources, value, "--source")
        except ValueError as exc:
            raise SystemExit(exc)
        with fitz.open(path) as document:
            texts = [(document[index].get_text() or "") for index in range(min(3, len(document)))]
            characters = sum(map(len, texts))
            verdict = "text" if characters > 200 else ("scan" if characters < 50 else "thin")
            print(f"{value}: {len(document)} pages, {characters} characters, {verdict}")


if __name__ == "__main__":
    main()
