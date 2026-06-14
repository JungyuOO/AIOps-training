#!/usr/bin/env python3
"""Check code-cell syntax for a notebook, skipping IPython magics."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path


def main() -> int:
    path = Path(sys.argv[1])
    notebook = json.loads(path.read_text(encoding="utf-8"))
    checked = 0
    skipped = 0
    for index, cell in enumerate(notebook["cells"]):
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", []))
        if source.lstrip().startswith("%"):
            skipped += 1
            continue
        try:
            ast.parse(source)
        except SyntaxError as exc:
            print(f"SYNTAX ERROR cell={index}: {exc}")
            print(source)
            return 1
        checked += 1
    print(f"checked={checked} skipped_magics={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
