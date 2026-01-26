#!/usr/bin/env python3
"""Compile text-based golden cases into a JSON file with current tags."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Optional

import chess

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from codex_utils import DEFAULT_ENGINE_PATH, analyze_position  # noqa: E402


@dataclass
class GoldenCase:
    case_id: str
    fen: str
    move: str
    move_uci: str
    description: str
    source_file: str
    label: str
    expected_tags: List[str]
    current_tags: List[str]

    def to_payload(self) -> dict:
        return {
            "id": self.case_id,
            "fen": self.fen,
            "move": self.move,
            "move_uci": self.move_uci,
            "description": self.description.strip(),
            "source_file": self.source_file,
            "label": self.label,
            "expected_tags": self.expected_tags,
            "current_tags": self.current_tags,
        }


class CaseParser:
    def __init__(self, path: Path):
        self.path = path
        self.lines = path.read_text(encoding="utf-8").splitlines()

    def parse(self) -> List[dict]:
        cases: List[dict] = []
        current: Optional[dict] = None

        for idx, line in enumerate(self.lines + [""]):
            header = self._parse_header(line)
            stripped = line.strip()

            if header:
                self._finalize_case(cases, current)
                label, index = header
                current = {
                    "label": label,
                    "index": index,
                    "source_file": self.path.name,
                    "description": "",
                }
                continue

            if not stripped:
                self._finalize_case(cases, current)
                current = None
                continue

            if current is None:
                raise ValueError(f"Unexpected content before header in {self.path}: '{line}' (line {idx + 1})")

            lowered = stripped.lower()
            if lowered.startswith("move:"):
                current["move"] = stripped.split(":", 1)[1].strip()
            elif lowered.startswith("explanation:"):
                explanation = stripped.split(":", 1)[1].strip()
                current["description"] = (current["description"] + " " + explanation).strip()
            elif "fen" not in current:
                current["fen"] = stripped
            else:
                current["description"] = (current["description"] + " " + stripped).strip()

        return cases

    def _finalize_case(self, cases: List[dict], case: Optional[dict]) -> None:
        if not case:
            return
        if "fen" not in case or "move" not in case:
            raise ValueError(f"Incomplete case in {self.path.name}: {case}")
        cases.append(case)

    @staticmethod
    def _parse_header(line: str) -> Optional[tuple[str, int]]:
        stripped = line.strip()
        if not stripped:
            return None
        # Header lines consist of alphabetic tokens followed by an integer (optional colon)
        if "/" in stripped:
            return None
        if not stripped.replace(":", " ").replace("_", " ").replace("-", " ").replace(" ", "").isalnum():
            return None
        parts = stripped.replace(":", " ").split()
        if len(parts) < 2 or not parts[-1].isdigit():
            return None
        label = " ".join(parts[:-1]).strip()
        return label, int(parts[-1])


def to_case_id(stem: str, index: int) -> str:
    return f"{stem}_{index:03d}"


def to_uci(fen: str, move_str: str) -> str:
    board = chess.Board(fen)
    try:
        move = board.parse_san(move_str)
        return move.uci()
    except ValueError:
        chess.Move.from_uci(move_str)  # will raise if invalid
        return move_str


def load_cases_from_folder(folder: Path) -> List[dict]:
    all_cases: List[dict] = []
    sequence_counters: dict[str, int] = {}
    for txt_file in sorted(folder.glob("*.txt")):
        parser = CaseParser(txt_file)
        parsed = parser.parse()
        stem = txt_file.stem
        sequence_counters.setdefault(stem, 0)
        for item in parsed:
            if "fen" not in item or "move" not in item:
                raise ValueError(f"Incomplete case in {txt_file}: {item}")
            sequence_counters[stem] += 1
            item["id"] = to_case_id(stem, sequence_counters[stem])
            item.setdefault("description", item["label"])
            all_cases.append(item)
    return all_cases


def analyse_cases(cases: List[dict], *, engine: str, use_new: bool) -> List[GoldenCase]:
    compiled: List[GoldenCase] = []
    for item in cases:
        fen = item["fen"]
        move_raw = item["move"]
        move_uci = to_uci(fen, move_raw)
        analysis = analyse_position(fen, move_uci, engine_path=engine, use_new=use_new)
        tags_primary = analysis["tags"].get("primary") or []
        tags_active = analysis["tags"].get("active") or []
        tags = _unique(tags_primary + tags_active)
        compiled.append(
            GoldenCase(
                case_id=item["id"],
                fen=fen,
                move=move_raw,
                move_uci=move_uci,
                description=item.get("description", ""),
                source_file=item.get("source_file", ""),
                label=item.get("label", ""),
                expected_tags=item.get("expected_tags", []),
                current_tags=tags,
            )
        )
    return compiled


def _unique(seq: Iterable[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for val in seq:
        if not val:
            continue
        if val not in seen:
            seen.add(val)
            ordered.append(val)
    return ordered


def analyse_position(fen: str, move_uci: str, engine_path: str, use_new: bool) -> dict:
    analysis = analyze_position(fen, move_uci, engine_path=engine_path, use_new=use_new)
    return analysis


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", default="tests/golden_cases", help="Folder containing *.txt case files")
    parser.add_argument("--output", default="tests/golden_cases/cases.json", help="Output JSON path")
    parser.add_argument("--engine", default=DEFAULT_ENGINE_PATH, help="Path to Stockfish")
    parser.add_argument("--legacy", action="store_true", help="Use legacy pipeline instead of new")
    parser.add_argument("--skip-current", action="store_true", help="Skip pipeline run (current_tags left empty)")
    args = parser.parse_args(list(argv) if argv is not None else None)

    folder = Path(args.folder)
    output_path = Path(args.output)
    cases = load_cases_from_folder(folder)

    if not args.skip_current:
        compiled = analyse_cases(cases, engine=args.engine, use_new=not args.legacy)
    else:
        compiled = [
            GoldenCase(
                case_id=item["id"],
                fen=item["fen"],
                move=item["move"],
                move_uci=to_uci(item["fen"], item["move"]),
                description=item.get("description", ""),
                source_file=item.get("source_file", ""),
                label=item.get("label", ""),
                expected_tags=item.get("expected_tags", []),
                current_tags=item.get("current_tags", []),
            )
            for item in cases
        ]

    payload = [case.to_payload() for case in compiled]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(payload)} cases to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
