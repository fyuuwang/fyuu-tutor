#!/usr/bin/env python3
"""Convert a text-layer PDF and optionally compare pdftotext output."""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from project_config import load_project, resolve_child, resolve_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root, config, _ = load_project(args.project)
    sources = resolve_path(root, config, "sources")
    try:
        source = resolve_child(sources, args.source, "--source")
        output = resolve_child(sources, args.output, "--output")
    except ValueError as exc:
        raise SystemExit(exc)
    if source == output:
        raise SystemExit("--source and --output must differ")
    result = subprocess.run(["markitdown", str(source)], capture_output=True, text=True, timeout=60)
    if result.returncode:
        print(result.stderr, file=sys.stderr)
        raise SystemExit(result.returncode)
    if shutil.which("pdftotext"):
        with tempfile.TemporaryDirectory() as temp:
            layout = Path(temp) / "layout.txt"
            subprocess.run(["pdftotext", "-layout", str(source), str(layout)], check=True, timeout=60)
            layout_size = len(layout.read_text(encoding="utf-8", errors="replace"))
            ratio = len(result.stdout) / layout_size if layout_size else 0
            print(f"pdftotext-layout: {layout_size} characters; ratio={ratio:.2f}")
    else:
        print("pdftotext-layout: skipped")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output.parent, delete=False) as handle:
        handle.write(result.stdout)
        temporary = Path(handle.name)
    temporary.replace(output)
    print(f"markitdown: {len(result.stdout)} characters -> {output}")


if __name__ == "__main__":
    main()
