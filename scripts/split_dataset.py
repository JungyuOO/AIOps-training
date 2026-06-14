#!/usr/bin/env python3
"""Create train/eval/gold full JSONL splits."""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path


def read_records(paths: list[Path]) -> list[dict]:
    records = []
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    records.append(json.loads(line))
    return records


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("data/curated"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument("--eval-ratio", type=float, default=0.15)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    by_category: dict[str, list[dict]] = defaultdict(list)
    for record in read_records(args.inputs):
        by_category[record["category"]].append(record)

    train: list[dict] = []
    eval_set: list[dict] = []
    gold: list[dict] = []
    for category in sorted(by_category):
        rows = by_category[category]
        rng.shuffle(rows)
        train_end = round(len(rows) * args.train_ratio)
        eval_end = train_end + round(len(rows) * args.eval_ratio)
        train.extend(rows[:train_end])
        eval_set.extend(rows[train_end:eval_end])
        gold.extend(rows[eval_end:])

    for rows in (train, eval_set, gold):
        rows.sort(key=lambda row: row["id"])

    write_jsonl(args.out_dir / "train.full.jsonl", train)
    write_jsonl(args.out_dir / "eval.full.jsonl", eval_set)
    write_jsonl(args.out_dir / "gold.full.jsonl", gold)
    print(f"train.full.jsonl: {len(train)}")
    print(f"eval.full.jsonl: {len(eval_set)}")
    print(f"gold.full.jsonl: {len(gold)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
