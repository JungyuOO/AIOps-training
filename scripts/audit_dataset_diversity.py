#!/usr/bin/env python3
"""Audit exact and normalized duplication in messages-only or full JSONL data."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


NOISE_PATTERNS = [
    re.compile(r"\b(?:train|eval|gold)-[a-z0-9_-]+-\d{5}\b"),
    re.compile(r"\b[a-z0-9-]+-(?:train|eval|gold)-\d{5}\b"),
    re.compile(r"\bcase_id:\s*\S+", re.IGNORECASE),
    re.compile(r"\b\d+\b"),
]


def normalize(text: str) -> str:
    lowered = text.lower()
    for pattern in NOISE_PATTERNS:
        lowered = pattern.sub("<var>", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def fingerprint(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def messages(record: dict) -> list[dict]:
    return record["messages"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()

    question_counts: Counter[str] = Counter()
    answer_counts: Counter[str] = Counter()
    pair_counts: Counter[str] = Counter()
    examples: dict[str, str] = {}
    total = 0

    for path in args.paths:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = json.loads(line)
                msgs = messages(record)
                user = msgs[1]["content"]
                assistant = msgs[2]["content"]
                q_fp = fingerprint(user)
                a_fp = fingerprint(assistant)
                p_fp = fingerprint(user + "\n---\n" + assistant)
                question_counts[q_fp] += 1
                answer_counts[a_fp] += 1
                pair_counts[p_fp] += 1
                examples.setdefault(p_fp, user[:500])
                total += 1

    def repeated(counter: Counter[str]) -> int:
        return sum(count for count in counter.values() if count > 1)

    print(f"TOTAL: {total}")
    print(f"UNIQUE_QUESTIONS: {len(question_counts)}")
    print(f"UNIQUE_ANSWERS: {len(answer_counts)}")
    print(f"UNIQUE_PAIRS: {len(pair_counts)}")
    print(f"REPEATED_QUESTION_ROWS: {repeated(question_counts)}")
    print(f"REPEATED_ANSWER_ROWS: {repeated(answer_counts)}")
    print(f"REPEATED_PAIR_ROWS: {repeated(pair_counts)}")
    print("TOP_REPEATED_PAIRS:")
    for fp, count in pair_counts.most_common(args.top):
        if count <= 1:
            break
        print(f"- count={count} fp={fp[:12]}")
        print(examples[fp].replace("\n", " ")[:240])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
