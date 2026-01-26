#!/usr/bin/env python3
"""
Apply Tag Renames

CLI tool to apply tag rename mappings to:
- Python source files
- JSON data files
- Test fixtures
- Documentation

This script performs in-place string replacement using the mappings
defined in rule_tagger2/versioning/tag_renames_v2.py.

Usage:
    # Dry run (show what would be changed)
    python3 scripts/apply_tag_renames.py --dry-run

    # Apply renames to all files
    python3 scripts/apply_tag_renames.py

    # Apply to specific directory
    python3 scripts/apply_tag_renames.py --path rule_tagger2/detectors

    # Apply to specific file pattern
    python3 scripts/apply_tag_renames.py --pattern "*.py"
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Add project root to path
script_dir = Path(__file__).parent
repo_root = script_dir.parent
sys.path.insert(0, str(repo_root))

from rule_tagger2.versioning.tag_renames_v2 import TAG_RENAMES


class TagRenameApplicator:
    """Applies tag rename mappings to files"""

    # File patterns to process
    DEFAULT_PATTERNS = [
        "*.py",
        "*.json",
        "*.yml",
        "*.yaml",
        "*.md",
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
    }

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.changes: List[Tuple[str, int, str, str]] = []  # (file, line, old, new)
        self.files_modified: Set[str] = set()

    def find_files(self, root_path: str, patterns: List[str]) -> List[str]:
        """Find all files matching patterns in root_path"""
        files = []
        root = Path(root_path)

        for pattern in patterns:
            for file_path in root.rglob(pattern):
                # Skip directories in SKIP_DIRS
                if any(skip in file_path.parts for skip in self.SKIP_DIRS):
                    continue

                if file_path.is_file():
                    files.append(str(file_path))

        return sorted(files)

    def apply_renames_to_file(self, file_path: str) -> int:
        """
        Apply renames to a single file.

        Returns:
            Number of replacements made
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except (UnicodeDecodeError, PermissionError) as e:
            print(f"⚠️  Skipping {file_path}: {e}", file=sys.stderr)
            return 0

        original_content = content
        replacements = 0

        # Apply each rename mapping
        for old_tag, new_tag in TAG_RENAMES.items():
            # Match whole words only (surrounded by quotes, whitespace, or delimiters)
            # This prevents renaming parts of longer identifiers
            pattern = rf'\b{re.escape(old_tag)}\b'

            matches = list(re.finditer(pattern, content))
            if matches:
                # Record changes for report BEFORE modifying content
                for match in matches:
                    # Find line number from ORIGINAL content
                    line_num = original_content[:match.start()].count('\n') + 1
                    self.changes.append((file_path, line_num, old_tag, new_tag))

                # Now apply the substitution
                content = re.sub(pattern, new_tag, content)
                replacements += len(matches)

        # Write back if changed
        if content != original_content:
            self.files_modified.add(file_path)

            if not self.dry_run:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)

        return replacements

    def apply_renames_bulk(self, files: List[str]) -> None:
        """Apply renames to multiple files"""
        total_replacements = 0

        for file_path in files:
            replacements = self.apply_renames_to_file(file_path)
            total_replacements += replacements

        print("")
        print("=" * 70)
        print("TAG RENAME APPLICATION SUMMARY")
        print("=" * 70)
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        print(f"Files scanned: {len(files)}")
        print(f"Files modified: {len(self.files_modified)}")
        print(f"Total replacements: {total_replacements}")
        print("=" * 70)

        if self.changes:
            print("")
            print("CHANGES MADE:" if not self.dry_run else "CHANGES TO BE MADE:")
            print("-" * 70)

            # Group by file
            by_file: Dict[str, List[Tuple[int, str, str]]] = {}
            for file_path, line_num, old_tag, new_tag in self.changes:
                if file_path not in by_file:
                    by_file[file_path] = []
                by_file[file_path].append((line_num, old_tag, new_tag))

            for file_path in sorted(by_file.keys()):
                print(f"\n📄 {file_path}")
                for line_num, old_tag, new_tag in by_file[file_path]:
                    print(f"   Line {line_num:4d}: {old_tag:30s} → {new_tag}")

        else:
            print("")
            print("✅ No renames applied (all tags already follow convention)")

        if self.dry_run and self.changes:
            print("")
            print("⚠️  DRY RUN MODE - No files were modified")
            print("   Run without --dry-run to apply changes")

        print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Apply tag rename mappings to codebase",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (show what would change)
  python3 scripts/apply_tag_renames.py --dry-run

  # Apply to all files
  python3 scripts/apply_tag_renames.py

  # Apply to specific directory
  python3 scripts/apply_tag_renames.py --path rule_tagger2/detectors

  # Apply to specific pattern
  python3 scripts/apply_tag_renames.py --pattern "*.json"
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without modifying files",
    )

    parser.add_argument(
        "--path",
        default=".",
        help="Root path to search for files (default: .)",
    )

    parser.add_argument(
        "--pattern",
        action="append",
        help="File pattern to match (can be specified multiple times)",
    )

    args = parser.parse_args()

    # Resolve patterns
    patterns = args.pattern if args.pattern else TagRenameApplicator.DEFAULT_PATTERNS

    # Check if any renames are defined
    if not TAG_RENAMES:
        print("✅ No renames defined in tag_renames_v2.py")
        print("   All tags already follow naming convention")
        sys.exit(0)

    print(f"Applying {len(TAG_RENAMES)} rename mapping(s)...")
    print(f"Searching: {args.path}")
    print(f"Patterns: {', '.join(patterns)}")
    print("")

    # Find files
    applicator = TagRenameApplicator(dry_run=args.dry_run)
    files = applicator.find_files(args.path, patterns)

    if not files:
        print("❌ No files found matching patterns", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(files)} file(s) to process")
    print("")

    # Apply renames
    applicator.apply_renames_bulk(files)


if __name__ == "__main__":
    main()
