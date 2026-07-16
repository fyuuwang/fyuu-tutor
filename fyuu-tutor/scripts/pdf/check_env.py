#!/usr/bin/env python3
"""Report optional tool availability for a configured project."""

import argparse
import importlib.util
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from project_config import load_project


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    load_project(args.project)
    for name in ("markitdown", "pdftotext", "pdftoppm"):
        print(f"command {name}: {'OK' if shutil.which(name) else 'MISSING'}")
    for name in ("fitz", "rapidocr_onnxruntime", "markitdown"):
        print(f"python {name}: {'OK' if importlib.util.find_spec(name) else 'MISSING'}")


if __name__ == "__main__":
    main()
