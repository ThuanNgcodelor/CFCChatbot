#!/usr/bin/env python3
"""Validate Vietnamese chatbot eval JSONL cases and summarize coverage."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


REQUIRED = {"id", "brand", "message", "expected_intent", "expected_mode", "risk"}
BRANDS = {"ZeO", "CFC"}
MODES = {"direct", "rewrite", "review", "clarify", "ignore"}
RISKS = {"low", "medium", "high"}


def load_cases(path: Path) -> tuple[list[dict], list[str]]:
    cases: list[dict] = []
    errors: list[str] = []
    seen: set[str] = set()

    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_no}: invalid JSON: {exc.msg}")
            continue

        missing = sorted(REQUIRED - set(item))
        if missing:
            errors.append(f"line {line_no}: missing fields: {', '.join(missing)}")

        case_id = str(item.get("id", ""))
        if case_id in seen:
            errors.append(f"line {line_no}: duplicate id: {case_id}")
        seen.add(case_id)

        if item.get("brand") not in BRANDS:
            errors.append(f"line {line_no}: brand must be one of {sorted(BRANDS)}")
        if item.get("expected_mode") not in MODES:
            errors.append(f"line {line_no}: expected_mode must be one of {sorted(MODES)}")
        if item.get("risk") not in RISKS:
            errors.append(f"line {line_no}: risk must be one of {sorted(RISKS)}")
        if not str(item.get("message", "")).strip():
            errors.append(f"line {line_no}: message must not be empty")

        cases.append(item)

    return cases, errors


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: check_eval_cases.py <cases.jsonl>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"Not found: {path}", file=sys.stderr)
        return 2

    cases, errors = load_cases(path)
    if errors:
        print("Eval case validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    by_brand = Counter(case["brand"] for case in cases)
    by_mode = Counter(case["expected_mode"] for case in cases)
    by_risk = Counter(case["risk"] for case in cases)
    no_accent = sum(1 for case in cases if str(case["message"]).isascii())
    abbreviations = sum(
        1
        for case in cases
        if any(token in f" {str(case['message']).lower()} " for token in [" k ", " ko ", " dc ", " dk ", " sdt ", " npp ", " cod "])
    )

    print(f"OK: {len(cases)} cases")
    print("By brand:", dict(sorted(by_brand.items())))
    print("By mode:", dict(sorted(by_mode.items())))
    print("By risk:", dict(sorted(by_risk.items())))
    print(f"No-accent/ascii messages: {no_accent}")
    print(f"Messages with common abbreviations: {abbreviations}")

    warnings: list[str] = []
    if len(cases) < 30:
        warnings.append("Add more cases before using this as a release gate; target at least 50 for each brand.")
    for brand in BRANDS:
        if by_brand[brand] < 10:
            warnings.append(f"Add more {brand} cases.")
    if by_mode["review"] == 0:
        warnings.append("Add review/escalation cases.")
    if abbreviations < 10:
        warnings.append("Add more abbreviation/short-chat cases.")

    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
