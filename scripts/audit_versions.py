"""CLI for auditing and normalizing rule_tagger output files."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Iterable

from rule_tagger2.versioning import detect_version, normalize_to_canon


def _iter_paths(patterns: Iterable[str]) -> Iterable[pathlib.Path]:
    for pattern in patterns:
        yield from pathlib.Path().glob(pattern)


def process_file(path: pathlib.Path, write_fixed: bool, out_dir: pathlib.Path) -> str:
    raw = json.loads(path.read_text(encoding="utf-8"))
    version = detect_version(raw)
    record = normalize_to_canon(raw)
    if write_fixed:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{path.stem}.fixed.json"
        out_path.write_text(json.dumps(record.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
    return version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit rule_tagger output versions.")
    parser.add_argument("patterns", nargs="+", help="Glob patterns for input files (e.g. reports/*.json)")
    parser.add_argument("--write-fixed", action="store_true", help="Write canonicalized copies")
    parser.add_argument("--out-dir", default="reports_fixed", help="Directory for canonicalized outputs")
    args = parser.parse_args(argv)

    out_dir = pathlib.Path(args.out_dir)
    counts: dict[str, int] = {}
    for path in sorted(_iter_paths(args.patterns)):
        if not path.is_file():
            continue
        try:
            version = process_file(path, args.write_fixed, out_dir)
            counts[version] = counts.get(version, 0) + 1
            print(f"[OK] {path} -> {version}")
        except Exception as exc:  # pragma: no cover - CLI diagnostics
            print(f"[ERR] {path}: {exc}", file=sys.stderr)

    if counts:
        print("\n== Version statistics ==")
        for version, count in sorted(counts.items(), key=lambda item: item[0]):
            print(f"{version:>24}: {count}")
    else:
        print("No files processed.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
