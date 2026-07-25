#!/usr/bin/env python3
"""OCR a page range from a private project PDF into a project source file."""

import argparse
import glob
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
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--start", required=True, type=int)
    parser.add_argument("--end", required=True, type=int)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--append", action="store_true")
    mode.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    root, config, _ = load_project(args.project)
    sources = resolve_path(root, config, "sources")
    from rapidocr_onnxruntime import RapidOCR
    engine = RapidOCR()
    chunks = []
    with tempfile.TemporaryDirectory() as temp:
        prefix = str(Path(temp) / "page")
        try:
            source = resolve_child(sources, args.source, "--source")
        except ValueError as exc:
            raise SystemExit(exc)
        subprocess.run(["pdftoppm", "-jpeg", "-r", "200", "-f", str(args.start), "-l", str(args.end), str(source), prefix], check=True)
        for image in sorted(glob.glob(f"{prefix}-*.jpg")):
            page = Path(image).stem.rsplit("-", 1)[-1].lstrip("0") or "0"
            result, _ = engine(image)
            text = "\n".join(row[1] for row in result) if result else ""
            chunks.append(f"\n<!-- page {page} -->\n{text}")
    try:
        output = resolve_child(sources, args.output, "--output")
    except ValueError as exc:
        raise SystemExit(exc)
    if output.exists() and not (args.append or args.overwrite):
        raise SystemExit(f"output exists; choose --append or --overwrite: {output}")
    if source == output:
        raise SystemExit("--source and --output must differ")
    output.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(chunks)
    if args.append and output.exists():
        content = output.read_text(encoding="utf-8") + content
    import tempfile as _tmp
    with _tmp.NamedTemporaryFile("w", encoding="utf-8", dir=output.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(output)
    print(f"OK {len(chunks)} pages -> {output}")


if __name__ == "__main__":
    main()
