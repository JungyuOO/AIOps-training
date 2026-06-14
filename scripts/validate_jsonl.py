#!/usr/bin/env python3
"""Validate OpenShift AIOps SFT JSONL files."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path


CATEGORIES = {
    "application_connectivity",
    "configuration_identity",
    "storage_data_artifacts",
    "accelerator_serving_runtime",
    "platform_lifecycle_capacity",
}
DIFFICULTIES = {"basic", "intermediate", "advanced"}
REQUIRED_FIELDS = {
    "id",
    "category",
    "difficulty",
    "expected_cause",
    "symptoms",
    "must_mention",
    "forbidden_actions",
    "source",
    "generator",
    "version",
    "messages",
}
REQUIRED_SECTIONS = [
    "[진단]",
    "[근거]",
    "[확인 명령어]",
    "[조치 방향]",
    "[주의사항]",
    "[추가 확인질문]",
]
DANGEROUS_OC = re.compile(r"\boc\s+(delete|patch|scale)\b|\boc\s+rollout\s+restart\b")
OC_COMMAND = re.compile(r"^\s*oc\s+\S+.*$", re.MULTILINE)
NAMESPACE_FLAG = re.compile(r"(\s-n\s+\S+|\s--namespace(?:=|\s+)\S+)")
ALL_NAMESPACES_FLAG = re.compile(r"(\s-A\b|\s--all-namespaces\b)")
NORMALIZE_PATTERNS = [
    re.compile(r"\b(?:train|eval|gold)-[a-z0-9_-]+-\d{5}\b"),
    re.compile(r"\b[a-z0-9-]+-(?:train|eval|gold)-\d{5}\b"),
    re.compile(r"\bcase_id:\s*\S+", re.IGNORECASE),
    re.compile(r"\b\d+\b"),
]


def normalize_for_diversity(text: str) -> str:
    lowered = text.lower()
    for pattern in NORMALIZE_PATTERNS:
        lowered = pattern.sub("<var>", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def diversity_fingerprint(user: str, assistant: str) -> str:
    normalized = normalize_for_diversity(user + "\n---\n" + assistant)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def load_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            text = line.strip()
            if not text:
                yield line_no, None, ["empty line"]
                continue
            try:
                yield line_no, json.loads(text), []
            except json.JSONDecodeError as exc:
                yield line_no, None, [f"invalid json: {exc.msg}"]


def validate_record(record: dict, seen_ids: set[str]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    missing = sorted(REQUIRED_FIELDS - set(record))
    if missing:
        errors.append(f"missing required fields: {', '.join(missing)}")

    sample_id = record.get("id")
    if isinstance(sample_id, str):
        if sample_id in seen_ids:
            errors.append(f"duplicate id: {sample_id}")
        seen_ids.add(sample_id)
    else:
        errors.append("id must be a string")

    if record.get("category") not in CATEGORIES:
        errors.append(f"invalid category: {record.get('category')!r}")
    if record.get("difficulty") not in DIFFICULTIES:
        errors.append(f"invalid difficulty: {record.get('difficulty')!r}")

    for field in ("symptoms", "must_mention", "forbidden_actions"):
        if not isinstance(record.get(field), list):
            errors.append(f"{field} must be a list")

    messages = record.get("messages")
    if not isinstance(messages, list) or len(messages) != 3:
        errors.append("messages must contain exactly 3 turns")
        return errors, warnings

    roles = [message.get("role") for message in messages if isinstance(message, dict)]
    if roles != ["system", "user", "assistant"]:
        errors.append(f"messages roles must be system,user,assistant; got {roles}")

    for idx, message in enumerate(messages):
        if not isinstance(message, dict):
            errors.append(f"message {idx} must be an object")
            continue
        if not str(message.get("content", "")).strip():
            errors.append(f"message {idx} content is empty")

    assistant = str(messages[2].get("content", ""))
    for section in REQUIRED_SECTIONS:
        if section not in assistant:
            errors.append(f"assistant missing section: {section}")

    commands = OC_COMMAND.findall(assistant)
    if not commands:
        errors.append("assistant must include oc verification commands")
    for command in commands:
        if " get nodes" in command or ALL_NAMESPACES_FLAG.search(command):
            continue
        if not NAMESPACE_FLAG.search(command):
            warnings.append(f"oc command lacks namespace: {command.strip()}")

    dangerous_commands = [command.strip() for command in commands if DANGEROUS_OC.search(command)]
    if dangerous_commands:
        warnings.append("assistant includes potentially dangerous oc action: " + "; ".join(dangerous_commands))

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--write-invalid", type=Path)
    parser.add_argument("--max-duplicate-pair", type=int, default=3)
    parser.add_argument("--min-unique-pair-ratio", type=float, default=0.95)
    args = parser.parse_args()

    valid = warn = error = 0
    invalid_rows: list[dict] = []
    seen_ids: set[str] = set()
    pair_counts: Counter[str] = Counter()
    pair_examples: dict[str, dict] = {}

    for path in args.paths:
        for line_no, record, parse_errors in load_jsonl(path):
            if parse_errors:
                error += 1
                invalid_rows.append({"file": str(path), "line": line_no, "errors": parse_errors})
                continue
            assert record is not None
            errors, warnings = validate_record(record, seen_ids)
            if not errors:
                msgs = record["messages"]
                fp = diversity_fingerprint(msgs[1]["content"], msgs[2]["content"])
                pair_counts[fp] += 1
                pair_examples.setdefault(fp, {"file": str(path), "line": line_no, "id": record.get("id")})
            if errors:
                error += 1
                invalid_rows.append(
                    {
                        "file": str(path),
                        "line": line_no,
                        "id": record.get("id"),
                        "errors": errors,
                        "warnings": warnings,
                    }
                )
            else:
                valid += 1
                if warnings:
                    warn += 1

    duplicate_failures = [
        (fp, count) for fp, count in pair_counts.items() if count > args.max_duplicate_pair
    ]
    total_pairs = sum(pair_counts.values())
    unique_ratio = (len(pair_counts) / total_pairs) if total_pairs else 1.0
    if duplicate_failures:
        error += len(duplicate_failures)
        for fp, count in sorted(duplicate_failures, key=lambda item: item[1], reverse=True)[:50]:
            invalid_rows.append(
                {
                    "errors": [f"normalized duplicate pair appears {count} times"],
                    "fingerprint": fp,
                    "example": pair_examples.get(fp),
                }
            )
    if unique_ratio < args.min_unique_pair_ratio:
        error += 1
        invalid_rows.append(
            {
                "errors": [
                    f"unique normalized pair ratio {unique_ratio:.4f} below minimum {args.min_unique_pair_ratio:.4f}"
                ],
                "unique_pairs": len(pair_counts),
                "total_pairs": total_pairs,
            }
        )

    if args.write_invalid:
        args.write_invalid.parent.mkdir(parents=True, exist_ok=True)
        with args.write_invalid.open("w", encoding="utf-8") as handle:
            for row in invalid_rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"VALID: {valid}")
    print(f"WARN: {warn}")
    print(f"ERROR: {error}")
    print(f"UNIQUE_PAIR_RATIO: {unique_ratio:.4f}")
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
