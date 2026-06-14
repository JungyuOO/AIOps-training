#!/usr/bin/env python3
"""Report category and difficulty balance for JSONL datasets."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    args = parser.parse_args()

    categories: Counter[str] = Counter()
    difficulties: Counter[str] = Counter()
    for path in args.inputs:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = json.loads(line)
                categories[record["category"]] += 1
                difficulties[record["difficulty"]] += 1

    print("CATEGORY")
    for key, value in sorted(categories.items()):
        print(f"{key}: {value}")
    print("DIFFICULTY")
    for key, value in sorted(difficulties.items()):
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
