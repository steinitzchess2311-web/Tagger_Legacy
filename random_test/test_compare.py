#!/usr/bin/env python3
"""
Compare Codex batch outputs against golden annotations.

Usage:
    python3 random_test/test_compare.py [--prefix intent_ --prefix prophylactic_]

Inputs:
    random_test/golden_sample.json                   (manual labels)
    random_test/random_test_results/*.json          (Codex outputs)

Outputs:
    random_test/test_results_improve/random_improve_X.csv
    random_test/test_results_improve/summary.txt
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set, Tuple

# Paths
BASE_DIR = Path(__file__).resolve().parent
GOLD_DIR = BASE_DIR / "golden_sample"
RESULT_DIR = BASE_DIR / "random_test_results"
OUTPUT_DIR = BASE_DIR / "test_results_improve"

MATCH_OK = "✅"
MATCH_FAIL = "❌"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare random test outputs with golden annotations.")
    parser.add_argument(
        "--prefix",
        action="append",
        default=[],
        help="Filter comparison to tags starting with this prefix (may be used multiple times).",
    )
    parser.add_argument(
        "--engine-field",
        default="tags",
        help="Key to read predicted tag list from (default: 'tags').",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def normalise_tags(tags: Iterable[str], prefixes: Sequence[str]) -> Set[str]:
    normalized = {str(tag) for tag in tags if tag}
    if not prefixes:
        return normalized
    return {tag for tag in normalized if any(tag.startswith(prefix) for prefix in prefixes)}


def load_golden_for_index(index: int, prefixes: Sequence[str]) -> List[Dict[str, object]]:
    path = GOLD_DIR / f"golden_sample_{index}.json"
    if not path.exists():
        raise FileNotFoundError(f"Golden sample file not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    normalized = []
    for entry in raw:
        fen = entry.get("fen") or entry.get("FEN")
        move = entry.get("move") or entry.get("MOVE")
        if not fen or not move:
            continue
        tags = entry.get("tags") or entry.get("gold_tags") or entry.get("label") or []
        if isinstance(tags, str):
            tags = [tag.strip() for tag in tags.split(",")]
        normalized.append(
            {
                "fen": fen,
                "move": move,
                "tags": normalise_tags(tags, prefixes),
                "raw_tags": tags,
            }
        )
    return normalized


def load_predictions(prefixes: Sequence[str], tag_field: str) -> List[Tuple[str, Path, List[Dict[str, object]]]]:
    if not RESULT_DIR.exists():
        raise FileNotFoundError(f"Result directory not found: {RESULT_DIR}")
    payloads: List[Tuple[str, Path, List[Dict[str, object]]]] = []
    for json_path in sorted(RESULT_DIR.glob("random_results_package_*.json")):
        data = json.loads(json_path.read_text(encoding="utf-8"))
        normalized = []
        for entry in data:
            fen = entry.get("fen")
            move = entry.get("move")
            if not fen or not move:
                continue
            tags = entry.get(tag_field) or entry.get("tags") or entry.get("tag") or []
            if isinstance(tags, str):
                tags = [tag.strip() for tag in tags.split(",")]
            normalized.append(
                {
                    "fen": fen,
                    "move": move,
                    "tags": normalise_tags(tags, prefixes),
                    "raw_tags": tags,
                    "delta": entry.get("delta") or entry.get("eval_delta") or 0.0,
                    "eval_before": entry.get("eval_before"),
                    "eval_played": entry.get("eval_played"),
                }
            )
        payloads.append((json_path.name, json_path, normalized))
    return payloads


def compute_differences(gold: Set[str], pred: Set[str]) -> Tuple[bool, Set[str], Set[str], Set[str], Set[str]]:
    true_pos = gold & pred
    false_pos = pred - gold
    false_neg = gold - pred
    match = not false_pos and not false_neg
    return match, true_pos, false_pos, false_neg, true_pos


def write_batch_csv(
    batch_index: int,
    records: List[Dict[str, object]],
    golden_records: List[Dict[str, object]],
    prefixes: Sequence[str],
) -> Tuple[int, int, Counter, Counter]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"random_improve_{batch_index}.csv"
    tp_total = fp_total = fn_total = 0
    mismatch_pairs: Counter[Tuple[str, str]] = Counter()
    per_tag_confusion: Counter[str] = Counter()

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["#", "FEN", "MOVE", "GOLD_TAGS", "PRED_TAGS", "MATCH", "DIFFERENCE", "Δeval", "NOTES"])

        for idx, (record, golden_entry) in enumerate(zip(records, golden_records), start=1):
            gold_tags = golden_entry.get("tags", set())
            pred_tags = record.get("tags", set())
            match, true_pos, false_pos, false_neg, _ = compute_differences(gold_tags, pred_tags)

            tp_total += len(true_pos)
            fp_total += len(false_pos)
            fn_total += len(false_neg)

            if false_pos or false_neg:
                for miss in false_neg or {"∅"}:
                    for extra in false_pos or {"∅"}:
                        mismatch_pairs[(miss, extra)] += 1
                for miss in false_neg:
                    per_tag_confusion[f"missing:{miss}"] += 1
                for extra in false_pos:
                    per_tag_confusion[f"extra:{extra}"] += 1

            difference_parts = []
            if false_neg:
                difference_parts.append("missing: " + ", ".join(sorted(false_neg)))
            if false_pos:
                difference_parts.append("extra: " + ", ".join(sorted(false_pos)))
            difference = " | ".join(difference_parts) if difference_parts else ""

            delta_eval = record.get("delta")
            try:
                delta_eval = float(delta_eval)
            except (TypeError, ValueError):
                delta_eval = ""

            writer.writerow(
                [
                    idx,
                    record["fen"],
                    record["move"],
                    " | ".join(sorted(gold_tags)) or "-",
                    " | ".join(sorted(pred_tags)) or "-",
                    MATCH_OK if match else MATCH_FAIL,
                    difference or "-",
                    f"{delta_eval:+.2f}" if isinstance(delta_eval, float) else "-",
                    "-",
                ]
            )

        # Summary block
        total_cases = len(records)
        match_cases = sum(
            1
            for record, golden_entry in zip(records, golden_records)
            if golden_entry.get("tags", set()) == record.get("tags", set())
        )
        mismatch_cases = total_cases - match_cases
        precision = tp_total / (tp_total + fp_total) if (tp_total + fp_total) else 0.0
        recall = tp_total / (tp_total + fn_total) if (tp_total + fn_total) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

        writer.writerow([])
        writer.writerow([f"Source bundle: {batch_index}"])
        writer.writerow([f"✅ MATCH: {match_cases}"])
        writer.writerow([f"❌ MISMATCH: {mismatch_cases}"])
        writer.writerow(
            [
                "Precision: {:.2f}  Recall: {:.2f}  F1: {:.2f}".format(
                    precision,
                    recall,
                    f1,
                )
            ]
        )

        if mismatch_pairs:
            writer.writerow(["Most common mismatches:"])
            for (miss, extra), count in mismatch_pairs.most_common(10):
                writer.writerow([f"  - {miss} → {extra} ({count})"])

    print(f"🧩 Writing batch report: {output_path} ...")
    return tp_total, fp_total, fn_total, mismatch_pairs


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    prefixes = args.prefix or []

    overall_tp = overall_fp = overall_fn = 0
    aggregate_mismatch: Counter[Tuple[str, str]] = Counter()

    for idx, golden_path in enumerate(sorted(GOLD_DIR.glob("golden_sample_*.json")), start=1):
        predictions_path = RESULT_DIR / f"random_results_package_{idx}.json"
        if not predictions_path.exists():
            print(f"⚠️ Skipping bundle {idx}: {predictions_path} not found.")
            continue
        golden_records = load_golden_for_index(idx, prefixes)
        predictions = json.loads(predictions_path.read_text(encoding="utf-8"))
        aligned_predictions = []
        for entry in predictions:
            tags = entry.get(args.engine_field) or entry.get("tags") or []
            if isinstance(tags, str):
                tags = [tag.strip() for tag in tags.split(",")]
            aligned_predictions.append(
                {
                    "fen": entry.get("fen"),
                    "move": entry.get("move"),
                    "tags": normalise_tags(tags, prefixes),
                    "raw_tags": tags,
                    "delta": entry.get("delta") or entry.get("eval_delta"),
                }
            )

        if len(aligned_predictions) != len(golden_records):
            print(f"⚠️ Bundle {idx}: size mismatch (gold {len(golden_records)} vs pred {len(aligned_predictions)}). Truncating to min.")
            min_len = min(len(aligned_predictions), len(golden_records))
            aligned_predictions = aligned_predictions[:min_len]
            golden_records = golden_records[:min_len]

        tp, fp, fn, mismatches = write_batch_csv(idx, aligned_predictions, golden_records, prefixes)
        overall_tp += tp
        overall_fp += fp
        overall_fn += fn
        aggregate_mismatch.update(mismatches)

    precision = overall_tp / (overall_tp + overall_fp) if (overall_tp + overall_fp) else 0.0
    recall = overall_tp / (overall_tp + overall_fn) if (overall_tp + overall_fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    summary_path = OUTPUT_DIR / "summary.txt"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8") as handle:
        handle.write("Global summary\n")
        handle.write(f"Precision: {precision:.4f}\n")
        handle.write(f"Recall: {recall:.4f}\n")
        handle.write(f"F1: {f1:.4f}\n\n")

        if aggregate_mismatch:
            handle.write("Top mismatch patterns:\n")
            for (miss, extra), count in aggregate_mismatch.most_common(10):
                handle.write(f"  - {miss} → {extra} ({count})\n")
    print(f"✅ Summary saved to {summary_path}")


if __name__ == "__main__":
    main()
