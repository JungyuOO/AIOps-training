#!/usr/bin/env python3
"""Score OpenShift AIOps SFT JSONL samples with rule-based heuristics."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


SECTIONS = ["[진단]", "[근거]", "[확인 명령어]", "[조치 방향]", "[주의사항]", "[추가 확인질문]"]
FIELD_HINTS = re.compile(
    r"spec\.|metadata\.|status\.|conditions|selector|labels|targetPort|secretKeyRef|"
    r"storageClassName|allocatable|limits|InstallPlan|OperatorGroup|ownerReferences|restartCount"
)
OC_NAMESPACED = re.compile(r"^\s*oc\s+.+(\s-n\s+\S+|\s--namespace(?:=|\s+)\S+)", re.MULTILINE)
DANGEROUS = re.compile(r"\boc\s+(delete|patch|scale)\b|\boc\s+rollout\s+restart\b")
OC_COMMAND = re.compile(r"^\s*oc\s+\S+.*$", re.MULTILINE)


def score_record(record: dict) -> dict:
    assistant = record["messages"][2]["content"]
    expected = str(record.get("expected_cause", "")).replace("_", " ")
    must_terms = [str(term) for term in record.get("must_mention", [])]

    structure = 3 if all(section in assistant for section in SECTIONS) else 1
    cause = 1
    diagnosis = assistant.split("[근거]", 1)[0]
    if record.get("expected_cause", "") in assistant or expected in assistant:
        cause = 3 if record.get("expected_cause", "") in diagnosis or expected in diagnosis else 2
    elif any(term in assistant for term in must_terms):
        cause = 2

    evidence_hits = len(set(FIELD_HINTS.findall(assistant)))
    evidence = min(3, evidence_hits)
    command = 3 if OC_NAMESPACED.search(assistant) else (1 if "oc " in assistant else 0)
    commands = OC_COMMAND.findall(assistant)
    safety = 1 if any(DANGEROUS.search(command) for command in commands) else 3

    total = structure + cause + evidence + command + safety
    if total >= 13:
        tier = "Gold"
    elif total >= 11:
        tier = "Silver"
    elif total >= 9:
        tier = "Bronze"
    else:
        tier = "Fail"

    return {
        "structure": structure,
        "cause": cause,
        "evidence": evidence,
        "command": command,
        "safety": safety,
        "total": total,
        "tier": tier,
    }


def iter_records(paths: list[Path]):
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--json-report", type=Path)
    parser.add_argument("--markdown-report", type=Path)
    args = parser.parse_args()

    grouped = defaultdict(list)
    scored_records = []
    for record in iter_records(args.paths):
        score = score_record(record)
        record["_score"] = score
        scored_records.append(record)
        grouped[record["category"]].append(score)

    writer = csv.writer(sys.stdout)
    header = ["category", "count", "avg_total", "structure", "cause", "evidence", "command", "safety", "gold", "silver", "fail"]
    writer.writerow(header)

    report = {"total": len(scored_records), "categories": {}}
    for category in sorted(grouped):
        rows = grouped[category]
        count = len(rows)
        summary = {
            "count": count,
            "avg_total": round(sum(row["total"] for row in rows) / count, 2),
            "structure": round(sum(row["structure"] for row in rows) / count, 2),
            "cause": round(sum(row["cause"] for row in rows) / count, 2),
            "evidence": round(sum(row["evidence"] for row in rows) / count, 2),
            "command": round(sum(row["command"] for row in rows) / count, 2),
            "safety": round(sum(row["safety"] for row in rows) / count, 2),
            "gold": sum(1 for row in rows if row["tier"] == "Gold"),
            "silver": sum(1 for row in rows if row["tier"] == "Silver"),
            "fail": sum(1 for row in rows if row["tier"] == "Fail"),
        }
        report["categories"][category] = summary
        writer.writerow([category, *summary.values()])

    if args.json_report:
        args.json_report.parent.mkdir(parents=True, exist_ok=True)
        args.json_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.markdown_report:
        lines = ["# Score Report", "", "| Category | Count | Avg / 15 | Gold | Silver | Fail |", "|---|---:|---:|---:|---:|---:|"]
        for category, summary in report["categories"].items():
            lines.append(
                f"| `{category}` | {summary['count']} | {summary['avg_total']} | {summary['gold']} | {summary['silver']} | {summary['fail']} |"
            )
        args.markdown_report.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    sys.exit(main())
