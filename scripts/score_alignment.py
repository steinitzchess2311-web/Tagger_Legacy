#!/usr/bin/env python3
"""
Compute alignment metrics between expected and current tags on the golden set.

Outputs:
* reports/alignment_by_tag.csv
* reports/alignment_summary.md
* reports/alignment_cases.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


DEFAULT_INPUT_CANDIDATES = [
    Path("tests") / "golden_cases" / "cases.json",
    Path("data") / "golden_cases.normalized.json",
    Path("tests") / "golden_cases.json",
]


def resolve_default_input() -> Path:
    for candidate in DEFAULT_INPUT_CANDIDATES:
        if candidate.exists():
            return candidate
    # Fallback to the last candidate so help text points to golden_cases.json if nothing exists yet.
    return DEFAULT_INPUT_CANDIDATES[-1]


DEFAULT_INPUT = resolve_default_input()
DEFAULT_REPORT_DIR = Path("reports") / "report_golden_sample"


@dataclass
class TagStats:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    support: int = 0

    @property
    def precision(self) -> Optional[float]:
        denom = self.tp + self.fp
        return self.tp / denom if denom else None

    @property
    def recall(self) -> Optional[float]:
        denom = self.tp + self.fn
        return self.tp / denom if denom else None

    @property
    def f1(self) -> Optional[float]:
        p = self.precision
        r = self.recall
        if not p or not r:
            return None
        denom = p + r
        return 2 * p * r / denom if denom else None


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score alignment between expected and current tags.")
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT),
        help="Path to data/golden_cases.normalized.json (default: %(default)s)",
    )
    parser.add_argument(
        "--reports-dir",
        default=str(DEFAULT_REPORT_DIR),
        help="Directory for alignment reports (default: %(default)s)",
    )
    return parser.parse_args(argv)


def load_cases(path: Path) -> List[dict]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        # Accept common wrappers like {"cases": [...]}
        for key in ("cases", "data", "items"):
            if key in data and isinstance(data[key], list):
                return data[key]
        raise ValueError(f"Unsupported JSON object structure in {path}")
    if not isinstance(data, list):
        raise ValueError(f"Expected a list of cases in {path}")
    return data


def to_tag_set(raw: Iterable[str]) -> List[str]:
    # Preserve deterministic order for readability by sorting.
    unique = sorted({tag for tag in raw if isinstance(tag, str)})
    return unique


def score_cases(cases: Sequence[dict]) -> Tuple[Dict[str, TagStats], List[dict]]:
    tag_stats: Dict[str, TagStats] = defaultdict(TagStats)
    case_rows: List[dict] = []

    for case in cases:
        case_id = str(case.get("id", ""))
        expected = to_tag_set(case.get("expected_tags", []) or [])
        current = to_tag_set(case.get("current_tags", []) or [])

        expected_set = set(expected)
        current_set = set(current)

        tp_tags = sorted(expected_set & current_set)
        fn_tags = sorted(expected_set - current_set)
        fp_tags = sorted(current_set - expected_set)

        for tag in expected_set:
            tag_stats[tag].support += 1
        for tag in tp_tags:
            tag_stats[tag].tp += 1
        for tag in fn_tags:
            tag_stats[tag].fn += 1
        for tag in fp_tags:
            tag_stats[tag].fp += 1

        case_rows.append(
            {
                "id": case_id,
                "miss": ";".join(fn_tags),
                "false": ";".join(fp_tags),
            }
        )

    # Ensure FP-only tags are accounted for even if never expected.
    for row in case_rows:
        for tag in row["false"].split(";"):
            if tag:
                _ = tag_stats[tag]

    case_rows.sort(key=lambda row: row["id"])
    return tag_stats, case_rows


def format_float(value: Optional[float]) -> str:
    return f"{value:.3f}" if value is not None else ""


def write_alignment_by_tag(path: Path, tag_stats: Dict[str, TagStats]) -> List[dict]:
    rows: List[dict] = []
    for tag, stats in tag_stats.items():
        rows.append(
            {
                "tag": tag,
                "support": stats.support,
                "tp": stats.tp,
                "fp": stats.fp,
                "fn": stats.fn,
                "precision": stats.precision,
                "recall": stats.recall,
                "f1": stats.f1,
            }
        )

    def sort_key(row: dict) -> Tuple[float, int, str]:
        recall = row["recall"] if row["recall"] is not None else 1.0
        return (recall, -row["support"], row["tag"])

    rows.sort(key=sort_key)

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["tag", "support", "tp", "fp", "fn", "precision", "recall", "f1"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "tag": row["tag"],
                    "support": row["support"],
                    "tp": row["tp"],
                    "fp": row["fp"],
                    "fn": row["fn"],
                    "precision": format_float(row["precision"]),
                    "recall": format_float(row["recall"]),
                    "f1": format_float(row["f1"]),
                }
            )
    return rows


def write_alignment_cases(path: Path, case_rows: Sequence[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["id", "miss", "false"])
        writer.writeheader()
        writer.writerows(case_rows)


def pick_top_misses(tag_rows: Sequence[dict], limit: int = 10) -> List[dict]:
    miss_rows = [row for row in tag_rows if row["fn"] > 0 and row["support"] > 0]
    miss_rows.sort(key=lambda row: (row["recall"] if row["recall"] is not None else 1.0, -row["support"], row["tag"]))
    return miss_rows[:limit]


def pick_top_false_positives(tag_rows: Sequence[dict], limit: int = 10) -> List[dict]:
    fp_rows = [row for row in tag_rows if row["fp"] > 0]
    fp_rows.sort(key=lambda row: (-row["fp"], -row["support"], row["tag"]))
    return fp_rows[:limit]


def overall_counts(tag_rows: Sequence[dict]) -> Tuple[int, int, int]:
    tp = sum(row["tp"] for row in tag_rows)
    fp = sum(row["fp"] for row in tag_rows)
    fn = sum(row["fn"] for row in tag_rows)
    return tp, fp, fn


def write_alignment_summary(
    path: Path,
    tag_rows: Sequence[dict],
    total_cases: int,
) -> None:
    tp_total, fp_total, fn_total = overall_counts(tag_rows)

    precision = tp_total / (tp_total + fp_total) if (tp_total + fp_total) else None
    recall = tp_total / (tp_total + fn_total) if (tp_total + fn_total) else None
    f1 = (
        (2 * precision * recall) / (precision + recall)
        if precision and recall and (precision + recall)
        else None
    )

    top_misses = pick_top_misses(tag_rows)
    top_false = pick_top_false_positives(tag_rows)

    def render_row(row: dict) -> str:
        return (
            f"| {row['tag']} | {row['support']} | {format_float(row['recall']) or '0.000'} "
            f"| {format_float(row['precision']) or '0.000'} | {format_float(row['f1']) or '0.000'} "
            f"| {row['tp']} | {row['fn']} | {row['fp']} |"
        )

    with path.open("w", encoding="utf-8") as fh:
        fh.write("# Alignment Summary\n\n")
        fh.write(f"- Cases evaluated: **{total_cases}**\n")
        fh.write(f"- Total TP: **{tp_total}**, FP: **{fp_total}**, FN: **{fn_total}**\n")
        fh.write(
            "- Micro precision: "
            f"**{format_float(precision) or '0.000'}**, recall: **{format_float(recall) or '0.000'}**, "
            f"F1: **{format_float(f1) or '0.000'}**\n\n"
        )

        fh.write("## Top-10 漏检标签\n")
        fh.write("| Tag | Support | Recall | Precision | F1 | TP | FN | FP |\n")
        fh.write("| --- | --- | --- | --- | --- | --- | --- | --- |\n")
        if top_misses:
            for row in top_misses:
                fh.write(f"{render_row(row)}\n")
        else:
            fh.write("| (none) | 0 | 0.000 | 0.000 | 0.000 | 0 | 0 | 0 |\n")

        fh.write("\n## Top-10 误检标签\n")
        fh.write("| Tag | Support | Recall | Precision | F1 | TP | FN | FP |\n")
        fh.write("| --- | --- | --- | --- | --- | --- | --- | --- |\n")
        if top_false:
            for row in top_false:
                fh.write(f"{render_row(row)}\n")
        else:
            fh.write("| (none) | 0 | 0.000 | 0.000 | 0.000 | 0 | 0 | 0 |\n")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    input_path = Path(args.input).resolve()
    reports_dir = Path(args.reports_dir).resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        print(f"[error] Input file not found: {input_path}", file=sys.stderr)
        return 1

    cases = load_cases(input_path)
    tag_stats, case_rows = score_cases(cases)

    by_tag_path = reports_dir / "alignment_by_tag.csv"
    summary_path = reports_dir / "alignment_summary.md"
    cases_path = reports_dir / "alignment_cases.csv"

    tag_rows = write_alignment_by_tag(by_tag_path, tag_stats)
    write_alignment_cases(cases_path, case_rows)
    write_alignment_summary(summary_path, tag_rows, total_cases=len(cases))

    print(f"[ok] Wrote {by_tag_path}")
    print(f"[ok] Wrote {summary_path}")
    print(f"[ok] Wrote {cases_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
