#!/usr/bin/env python3
"""Render and OCR selected pages from private project sources for comparison."""

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from project_config import load_project, resolve_child, resolve_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--sample", action="append", required=True, help="relative.pdf:page:label")
    args = parser.parse_args()
    root, config, _ = load_project(args.project)
    sources = resolve_path(root, config, "sources")
    from rapidocr_onnxruntime import RapidOCR
    engine = RapidOCR()
    for sample in args.sample:
        relative, page, label = sample.split(":", 2)
        try:
            source = resolve_child(sources, relative, "--sample source")
        except ValueError as exc:
            raise SystemExit(exc)
        with tempfile.TemporaryDirectory() as temp:
            prefix = str(Path(temp) / "page")
            subprocess.run(["pdftoppm", "-jpeg", "-r", "200", "-f", page, "-l", page, str(source), prefix], check=True)
            images = list(Path(temp).glob("page-*.jpg"))
            if not images:
                raise SystemExit(f"render failed: {sample}")
            result, _ = engine(str(images[0]))
            text = "\n".join(row[1] for row in result) if result else ""
            print(f"===== {label} p{page} =====\n{text[:600]}")


if __name__ == "__main__":
    main()
