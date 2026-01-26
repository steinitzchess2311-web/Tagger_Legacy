#!/usr/bin/env python3
"""
Scan Tag Usage

Scans the codebase for hardcoded tag name strings and reports:
- File locations where tags are referenced
- Line numbers and context
- Whether tags are defined in tag_catalog.yml
- Potential issues (undefined tags, deprecated tags)

This helps identify places that need updating when tag names change.

Usage:
    # Scan entire codebase
    python3 scripts/scan_tag_usage.py

    # Scan specific directory
    python3 scripts/scan_tag_usage.py --path rule_tagger2/detectors

    # Include test files
    python3 scripts/scan_tag_usage.py --include-tests

    # Export to JSON
    python3 scripts/scan_tag_usage.py --output reports/tag_usage.json
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import yaml


class TagUsageScanner:
    """Scans codebase for hardcoded tag name references"""

    # File patterns to scan
    SCAN_PATTERNS = [
        "*.py",
    ]

    # Directories to skip
    SKIP_DIRS = {
        "__pycache__",
        ".git",
        ".pytest_cache",
        "node_modules",
        "venv",
        ".venv",
        "build",
        "dist",
        "reports",
    }

    # Patterns that match string literal tag names only
    # DOES NOT match attribute access (result.tag_name) to avoid false positives
    TAG_PATTERNS = [
        # Tags being appended/added to collections: result.tags.append("tag_name")
        r'\.(?:tags|applied_tags)\.(?:append|add|extend)\s*\(\s*["\']([a-z_][a-z0-9_]*)["\']',
        # Tags in result constructors: TagResult(..., tags=["tag_name"])
        r'tags\s*=\s*\[?\s*["\']([a-z_][a-z0-9_]*)["\']',
        # Tags in assertions/checks: if "tag_name" in result.tags
        r'["\']([a-z_][a-z0-9_]*)["\'][\s\)]*\s+in\s+(?:\w+\.)?tags',
        # hasattr checks on TagResult/result: hasattr(result, "tag_name")
        r'hasattr\s*\(\s*(?:result|tag_result|res|legacy_result)\s*,\s*["\']([a-z_][a-z0-9_]*)["\']',
        # getattr calls on TagResult/result: getattr(result, "tag_name", False)
        r'getattr\s*\(\s*(?:result|tag_result|res|legacy_result)\s*,\s*["\']([a-z_][a-z0-9_]*)["\']',
        # setattr calls on TagResult/result: setattr(result, "tag_name", True)
        r'setattr\s*\(\s*(?:result|tag_result|res|legacy_result)\s*,\s*["\']([a-z_][a-z0-9_]*)["\']',
    ]

    def __init__(
        self,
        catalog_path: str,
        include_tests: bool = False,
        min_context_lines: int = 1,
    ):
        self.catalog_path = catalog_path
        self.include_tests = include_tests
        self.min_context_lines = min_context_lines

        self.known_tags: Set[str] = set()
        self.deprecated_tags: Set[str] = set()
        self.usages: Dict[str, List[Tuple[str, int, str]]] = defaultdict(list)
        self.undefined_tags: Dict[str, List[Tuple[str, int, str]]] = defaultdict(list)

        # Load catalog
        self.load_catalog()

    def load_catalog(self) -> None:
        """Load tag catalog to get known tags"""
        try:
            with open(self.catalog_path, "r", encoding="utf-8") as f:
                catalog = yaml.safe_load(f)

            # Extract tag names
            for tag_name, tag_meta in catalog.items():
                if tag_name in ["schema_version", "control_schema_version"]:
                    continue

                self.known_tags.add(tag_name)

                # Track deprecated tags
                if tag_meta.get("deprecated", False):
                    self.deprecated_tags.add(tag_name)

                # Track aliases
                aliases = tag_meta.get("aliases", [])
                for alias in aliases:
                    self.known_tags.add(alias)

            print(f"✅ Loaded {len(self.known_tags)} known tags from catalog")

        except FileNotFoundError:
            print(f"⚠️  Warning: Catalog not found at {self.catalog_path}", file=sys.stderr)
            print("   Will report all found tags as undefined", file=sys.stderr)
        except yaml.YAMLError as e:
            print(f"❌ Error parsing catalog: {e}", file=sys.stderr)
            sys.exit(1)

    def should_skip_file(self, file_path: str) -> bool:
        """Check if a file should be skipped"""
        # Skip test files unless explicitly included
        if not self.include_tests and "test" in file_path.lower():
            return True

        # Skip specific files
        if "tag_catalog.yml" in file_path:
            return True

        if "tag_renames" in file_path:
            return True

        if "scan_tag_usage.py" in file_path:
            return True

        return False

    def find_files(self, root_path: str) -> List[str]:
        """Find all Python files to scan"""
        files = []
        root = Path(root_path)

        for pattern in self.SCAN_PATTERNS:
            for file_path in root.rglob(pattern):
                # Skip directories in SKIP_DIRS
                if any(skip in file_path.parts for skip in self.SKIP_DIRS):
                    continue

                if self.should_skip_file(str(file_path)):
                    continue

                if file_path.is_file():
                    files.append(str(file_path))

        return sorted(files)

    def extract_tags_from_line(self, line: str) -> Set[str]:
        """Extract potential tag names from a line of code"""
        candidates = set()

        for pattern in self.TAG_PATTERNS:
            matches = re.finditer(pattern, line)
            for match in matches:
                candidate = match.group(1)

                # Filter out obvious non-tags
                if self.is_likely_tag(candidate):
                    candidates.add(candidate)

        return candidates

    def is_likely_tag(self, candidate: str) -> bool:
        """
        Check if a candidate string looks like a tag based on naming conventions.

        Returns True if the candidate follows tag naming patterns.
        We intentionally accept candidates NOT in the catalog so we can
        report undefined tags for CI gating.
        """
        # Basic snake_case validation
        if not re.match(r'^[a-z][a-z0-9_]*$', candidate):
            return False

        # Exclude common non-tag identifiers
        EXCLUDED_NAMES = {
            # Common Python keywords/builtins
            'self', 'cls', 'result', 'context', 'move', 'board', 'engine',
            'tags', 'name', 'value', 'data', 'config', 'path', 'file',
            'line', 'text', 'message', 'error', 'info', 'debug', 'warning',
            'true', 'false', 'none', 'return', 'yield', 'pass', 'break',

            # TagResult data fields (not tag names)
            'analysis_context', 'analysis_meta', 'played_move', 'fen_before',
            'eval_before', 'eval_played', 'eval_best', 'eval_after',
            'metrics_before', 'metrics_played', 'opp_metrics_before',
            'component_deltas', 'coverage_delta', 'tactical_weight',
            'mode', 'maneuver_precision_score', 'multipv', 'plan_loss',
            'reasons', 'runtime_ms', 'sampled', 'stable',
            'variance_after', 'variance_before', 'to_dict', 'detected',
            'snapshot', 'copy', 'engine_meta', 'phase', 'actor',
        }
        if candidate in EXCLUDED_NAMES:
            return False

        # Accept all other snake_case candidates (will classify as known/undefined later)
        return True

    def scan_file(self, file_path: str) -> None:
        """Scan a single file for tag usages"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except (UnicodeDecodeError, PermissionError):
            return

        for line_num, line in enumerate(lines, start=1):
            tags = self.extract_tags_from_line(line)

            for tag in tags:
                context = line.strip()

                # Classify as known or undefined
                if tag in self.known_tags:
                    self.usages[tag].append((file_path, line_num, context))
                else:
                    self.undefined_tags[tag].append((file_path, line_num, context))

    def scan_all(self, files: List[str]) -> None:
        """Scan all files"""
        print(f"Scanning {len(files)} file(s)...")
        for file_path in files:
            self.scan_file(file_path)

    def print_report(self) -> None:
        """Print scan report to console"""
        print("")
        print("=" * 80)
        print("TAG USAGE SCAN REPORT")
        print("=" * 80)
        print(f"Known tags (from catalog): {len(self.known_tags)}")
        print(f"Tags found in code: {len(self.usages)}")
        print(f"Undefined tags found: {len(self.undefined_tags)}")
        print(f"Deprecated tag usages: {sum(1 for t in self.usages if t in self.deprecated_tags)}")
        print("=" * 80)

        # Report undefined tags (CI gate blocker)
        if self.undefined_tags:
            print("")
            print("❌ UNDEFINED TAG USAGES (NOT IN CATALOG):")
            print("-" * 80)
            for tag in sorted(self.undefined_tags.keys()):
                print(f"  • {tag}:")
                for file_path, line_num, context in self.undefined_tags[tag][:5]:  # Show first 5
                    print(f"      {file_path}:{line_num}")
                    print(f"        {context}")
                if len(self.undefined_tags[tag]) > 5:
                    print(f"      ... and {len(self.undefined_tags[tag]) - 5} more")
            print("")
            print("⚠️  CI GATE: These tags must be registered in tag_catalog.yml")
            print("    or removed from the code before merging.")

        # Report deprecated tag usages
        deprecated_usages = {t: locs for t, locs in self.usages.items() if t in self.deprecated_tags}
        if deprecated_usages:
            print("")
            print("⚠️  DEPRECATED TAG USAGES:")
            print("-" * 80)
            for tag in sorted(deprecated_usages.keys()):
                print(f"  • {tag}:")
                for file_path, line_num, context in deprecated_usages[tag][:5]:  # Show first 5
                    print(f"      {file_path}:{line_num}")
                if len(deprecated_usages[tag]) > 5:
                    print(f"      ... and {len(deprecated_usages[tag]) - 5} more")

        # Top 10 most-used tags
        sorted_tags = sorted(self.usages.items(), key=lambda x: len(x[1]), reverse=True)
        top_10 = sorted_tags[:10]

        print("")
        print("📊 TOP 10 MOST-USED TAGS:")
        print("-" * 80)
        for tag, locations in top_10:
            status = " [DEPRECATED]" if tag in self.deprecated_tags else ""
            print(f"  {len(locations):3d}x  {tag}{status}")

        if not self.usages:
            print("  (No tag usages found)")

        print("=" * 80)

    def export_json(self, output_path: str) -> None:
        """Export scan results to JSON"""
        report = {
            "summary": {
                "known_tags": len(self.known_tags),
                "tags_found": len(self.usages),
                "undefined_tags_found": len(self.undefined_tags),
                "deprecated_usages": sum(1 for t in self.usages if t in self.deprecated_tags),
            },
            "deprecated_tags": sorted(list(self.deprecated_tags)),
            "usages": {},
            "undefined_usages": {},
        }

        # Format known tag usages
        for tag, locations in self.usages.items():
            report["usages"][tag] = {
                "count": len(locations),
                "locations": [
                    {
                        "file": file_path,
                        "line": line_num,
                        "context": context,
                    }
                    for file_path, line_num, context in locations
                ],
                "status": "deprecated" if tag in self.deprecated_tags else "ok",
            }

        # Format undefined tag usages
        for tag, locations in self.undefined_tags.items():
            report["undefined_usages"][tag] = {
                "count": len(locations),
                "locations": [
                    {
                        "file": file_path,
                        "line": line_num,
                        "context": context,
                    }
                    for file_path, line_num, context in locations
                ],
            }

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"✅ JSON report written to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Scan codebase for hardcoded tag name usages")
    parser.add_argument(
        "--path",
        default=".",
        help="Root path to scan (default: .)",
    )
    parser.add_argument(
        "--catalog",
        default="rule_tagger2/core/tag_catalog.yml",
        help="Path to tag_catalog.yml (default: rule_tagger2/core/tag_catalog.yml)",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files in scan (default: False)",
    )
    parser.add_argument(
        "--output",
        help="Export results to JSON file (optional)",
    )

    args = parser.parse_args()

    # Resolve paths
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    if Path(args.catalog).is_absolute():
        catalog_path = args.catalog
    else:
        catalog_path = str(repo_root / args.catalog)

    # Initialize scanner
    scanner = TagUsageScanner(
        catalog_path=catalog_path,
        include_tests=args.include_tests,
    )

    # Find and scan files
    files = scanner.find_files(args.path)
    if not files:
        print("❌ No Python files found to scan", file=sys.stderr)
        sys.exit(1)

    scanner.scan_all(files)

    # Print report
    scanner.print_report()

    # Export JSON if requested
    if args.output:
        scanner.export_json(args.output)

    # Exit with error code if undefined tags found (for CI gating)
    if scanner.undefined_tags:
        print("")
        print(f"❌ FAIL: Found {len(scanner.undefined_tags)} undefined tag(s)", file=sys.stderr)
        print("   Register these tags in tag_catalog.yml or remove them from code.", file=sys.stderr)
        sys.exit(1)

    print("")
    print("✅ PASS: All tags are registered in the catalog")


if __name__ == "__main__":
    main()
