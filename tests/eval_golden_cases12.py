#!/usr/bin/env python3
"""Evaluate the golden samples in cases1.json and cases2.json against their expected tags."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

CASE_FILES = [
    Path(__file__).resolve().parent / "golden_cases" / "cases1.json",
    Path(__file__).resolve().parent / "golden_cases" / "cases2.json",
]

REPORT_DIR = Path(__file__).resolve().parents[1] / "reports" / "report_golden_sample"
SUMMARY_JSON = REPORT_DIR / "summary.json"
SUMMARY_TXT = REPORT_DIR / "summary.txt"

IGNORED_TAGS = {"forced_move"}


def _load_alias_module() -> Any:
    alias_path = Path(__file__).resolve().parents[1] / "rule_tagger2" / "versioning" / "tag_aliases.py"
    spec = importlib.util.spec_from_file_location("rule_tagger2_tag_aliases", alias_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load tag_aliases module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_ALIAS_MODULE = _load_alias_module()


def _canonicalize_tags(tags: List[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for tag in tags:
        canonical = _ALIAS_MODULE.get_canonical_name(tag)
        if canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return result


def _filter_tags(tags: List[str]) -> List[str]:
    return [tag for tag in tags if tag not in IGNORED_TAGS]


def load_cases() -> List[Dict[str, Any]]:
    all_cases: List[Dict[str, Any]] = []
    for path in CASE_FILES:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, list):
            raise ValueError(f"{path} does not contain a list of cases.")
        all_cases.extend(data)
    return all_cases


def compare_tags(expected: List[str], current: List[str]) -> Tuple[List[str], List[str]]:
    exp_set = set(expected)
    cur_set = set(current)
    missing = sorted(exp_set - cur_set)
    extra = sorted(cur_set - exp_set)
    return missing, extra


def summarize_cases(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    labeled = 0
    perfect = 0
    total_missing = 0
    total_extra = 0
    per_tag: Dict[str, Dict[str, int]] = {}
    mismatch_details: List[Dict[str, Any]] = []
    extra_tag_counts: Dict[str, int] = {}

    for case in cases:
        raw_expected = case.get("expected_tags") or []
        if not raw_expected:
            continue
        expected = _filter_tags(_canonicalize_tags(raw_expected))
        current = _filter_tags(_canonicalize_tags(case.get("current_tags") or []))
        labeled += 1
        missing, extra = compare_tags(expected, current)
        if not missing and not extra:
            perfect += 1
        else:
            total_missing += len(missing)
            total_extra += len(extra)
            mismatch_details.append(
                {
                    "id": case.get("id"),
                    "fen": case.get("fen"),
                    "move_uci": case.get("move_uci"),
                    "expected": expected,
                    "current": current,
                    "missing": missing,
                    "extra": extra,
                }
            )
        for tag in expected:
            stats = per_tag.setdefault(tag, {"expected": 0, "hit": 0})
            stats["expected"] += 1
            if tag in current:
                stats["hit"] += 1
        for tag in extra:
            extra_tag_counts[tag] = extra_tag_counts.get(tag, 0) + 1

    per_tag_stats = {
        tag: {
            "expected": stats["expected"],
            "hit": stats["hit"],
            "hit_rate": stats["hit"] / stats["expected"] if stats["expected"] else 0.0,
        }
        for tag, stats in sorted(per_tag.items())
    }
    extra_sorted = sorted(extra_tag_counts.items(), key=lambda entry: (-entry[1], entry[0]))

    return {
        "labeled_cases": labeled,
        "perfect_cases": perfect,
        "total_missing_tags": total_missing,
        "total_extra_tags": total_extra,
        "per_tag_stats": per_tag_stats,
        "extra_tag_stats": {
            tag: count
            for tag, count in extra_sorted
        },
        "top_extra_tags": [
            {"tag": tag, "count": count} for tag, count in extra_sorted[:10]
        ],
        "mismatches": mismatch_details,
    }


def format_summary_text(summary: Dict[str, Any]) -> str:
    parts: List[str] = []
    parts.append("Golden evaluation (cases1 + cases2)")
    parts.append(f"labeled_cases        : {summary['labeled_cases']}")
    parts.append(f"perfect_cases        : {summary['perfect_cases']}")
    parts.append(f"total_missing_tags   : {summary['total_missing_tags']}")
    parts.append(f"total_extra_tags     : {summary['total_extra_tags']}")
    parts.append("")
    parts.append("Per-tag hit rates:")
    for tag, stats in summary["per_tag_stats"].items():
        hit = stats["hit"]
        exp = stats["expected"]
        rate = stats["hit_rate"]
        parts.append(f"  {tag:30s} {hit:3d}/{exp:3d} ({rate:.1%})")
    parts.append("")
    parts.append("Most common extra tags:")
    top_extra = summary.get("top_extra_tags") or []
    if top_extra:
        for entry in top_extra:
            parts.append(f"  {entry['tag']:30s} {entry['count']:3d}")
    else:
        parts.append("  (none)")
    parts.append("")
    parts.append("Sample mismatches (first 20):")
    for mismatch in summary["mismatches"][:20]:
        tag_list = mismatch["move_uci"] or "??"
        parts.append(f"- {mismatch.get('id')} move {tag_list}")
        parts.append(f"  expected: {mismatch['expected']}")
        parts.append(f"  current : {mismatch['current']}")
        parts.append(f"  missing : {mismatch['missing']}")
        parts.append(f"  extra   : {mismatch['extra']}")
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    cases = load_cases()
    summary = summarize_cases(cases)
    with SUMMARY_JSON.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False)
    with SUMMARY_TXT.open("w", encoding="utf-8") as handle:
        handle.write(format_summary_text(summary))


if __name__ == "__main__":
    main()
