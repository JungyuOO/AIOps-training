#!/usr/bin/env python3
"""Export metadata-rich JSONL to messages-only training JSONL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def export(input_path: Path, output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with input_path.open("r", encoding="utf-8") as src, output_path.open("w", encoding="utf-8") as dst:
        for line in src:
            if not line.strip():
                continue
            record = json.loads(line)
            dst.write(json.dumps({"messages": record["messages"]}, ensure_ascii=False) + "\n")
            count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    count = export(args.input, args.output)
    print(f"EXPORTED: {count} {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
