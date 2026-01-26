#!/usr/bin/env python3
"""
CI Tag Lint - Continuous Integration guard for tag naming and hierarchy consistency.

This script runs two critical checks:
1. Tag Name Lint: Scans for hardcoded tag strings and verifies they exist in tag_catalog.yml
2. Hierarchy Consistency: Validates parent-child relationships, aliases, and detector references

Exit codes:
  0 - All checks passed
  1 - Tag name violations found (unregistered tags in code)
  2 - Hierarchy consistency violations found
  3 - Both tag name and hierarchy violations found

Usage:
  python3 scripts/ci_tag_lint.py [--strict] [--path PATH]

Options:
  --strict: Treat warnings as errors
  --path: Limit scan to specific directory (default: rule_tagger2/)
"""
import argparse
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.scan_tag_usage import TagUsageScanner
from rule_tagger2.core.tag_schema_validator import TagSchemaValidator


class CITagLint:
    """CI guard for tag naming and hierarchy consistency."""

    def __init__(self, strict: bool = False, scan_path: str = "rule_tagger2"):
        """
        Initialize CI lint checker.

        Args:
            strict: If True, treat warnings as errors
            scan_path: Directory to scan for tag usage
        """
        self.strict = strict
        self.scan_path = scan_path
        self.violations = []

    def run_tag_name_lint(self) -> tuple[bool, int]:
        """
        Run tag name lint check.

        Scans code for hardcoded tag strings and verifies they're registered
        in tag_catalog.yml.

        Returns:
            (passed, violation_count) tuple
        """
        print("=" * 60)
        print("CI CHECK 1: Tag Name Lint")
        print("=" * 60)
        print()

        catalog_path = "rule_tagger2/core/tag_catalog.yml"
        scanner = TagUsageScanner(catalog_path)

        # Load catalog
        scanner.load_catalog()

        # Scan for tag usage
        print(f"Scanning {self.scan_path}/ for hardcoded tag strings...")
        files = scanner.find_files(self.scan_path)

        if not files:
            print(f"⚠️  No Python files found in {self.scan_path}/")
            return (True, 0)

        scanner.scan_all(files)

        # Check for unregistered tags (now stored in scanner.undefined_tags)
        unregistered = []
        deprecated_used = []

        # Convert undefined tags to list format
        for tag_name, usages_list in scanner.undefined_tags.items():
            locations = [
                {"file": file_path, "line": line_no, "context": context}
                for file_path, line_no, context in usages_list
            ]
            unregistered.append((tag_name, locations))

        # Check for deprecated tag usage
        for tag_name, usages_list in scanner.usages.items():
            if tag_name in scanner.deprecated_tags:
                locations = [
                    {"file": file_path, "line": line_no, "context": context}
                    for file_path, line_no, context in usages_list
                ]
                deprecated_used.append((tag_name, locations))

        # Report unregistered tags (hard error)
        if unregistered:
            print(f"❌ FAIL: Found {len(unregistered)} unregistered tag(s)")
            print()
            for tag_name, locations in unregistered:
                print(f"  Tag: '{tag_name}'")
                print(f"  Locations ({len(locations)}):")
                for loc in locations[:3]:  # Show first 3 locations
                    print(f"    - {loc['file']}:{loc['line']}")
                if len(locations) > 3:
                    print(f"    ... and {len(locations) - 3} more")
                print()

            self.violations.append({
                "check": "tag_name_lint",
                "severity": "error",
                "count": len(unregistered),
                "details": [
                    {"tag": tag, "locations": locs}
                    for tag, locs in unregistered
                ],
            })

        # Report deprecated tags (warning or error based on strict mode)
        if deprecated_used:
            severity = "ERROR" if self.strict else "WARNING"
            symbol = "❌" if self.strict else "⚠️"
            print(f"{symbol} {severity}: Found {len(deprecated_used)} deprecated tag(s)")
            print()
            for tag_name, locations in deprecated_used:
                print(f"  Tag: '{tag_name}' (deprecated)")
                print(f"  Locations ({len(locations)}):")
                for loc in locations[:3]:
                    print(f"    - {loc['file']}:{loc['line']}")
                if len(locations) > 3:
                    print(f"    ... and {len(locations) - 3} more")
                print()

            self.violations.append({
                "check": "tag_name_lint",
                "severity": "error" if self.strict else "warning",
                "count": len(deprecated_used),
                "details": [
                    {"tag": tag, "locations": locs, "deprecated": True}
                    for tag, locs in deprecated_used
                ],
            })

        # Summary
        total_issues = len(unregistered) + (len(deprecated_used) if self.strict else 0)

        if total_issues == 0:
            print("✅ PASS: All hardcoded tags are registered in tag_catalog.yml")
            if deprecated_used and not self.strict:
                print(f"⚠️  Note: {len(deprecated_used)} deprecated tag(s) found (warnings only)")

        print()
        return (total_issues == 0, total_issues)

    def run_hierarchy_consistency_check(self) -> tuple[bool, int]:
        """
        Run hierarchy consistency check.

        Validates tag catalog structure including parent-child relationships,
        aliases, and detector references.

        Returns:
            (passed, violation_count) tuple
        """
        print("=" * 60)
        print("CI CHECK 2: Hierarchy Consistency")
        print("=" * 60)
        print()

        catalog_path = "rule_tagger2/core/tag_catalog.yml"

        print(f"Validating {catalog_path}...")

        # Create validator and run checks
        validator = TagSchemaValidator(catalog_path, strict=self.strict)

        if not validator.load_catalog():
            print("❌ FAIL: Could not load tag catalog")
            return (False, 1)

        is_valid = validator.validate()

        # Collect errors and warnings
        errors = [str(e) for e in validator.errors]
        warnings = [str(w) for w in validator.warnings]

        # Determine pass/fail
        tags_count = len(validator.catalog)

        if is_valid and (not self.strict or not warnings):
            print(f"✅ PASS: Tag catalog is valid")
            print(f"   Tags validated: {tags_count}")
            if warnings and not self.strict:
                print(f"⚠️  Note: {len(warnings)} warning(s) (non-blocking)")
        else:
            print(f"❌ FAIL: Tag catalog validation failed")
            print(f"   Errors: {len(errors)}")
            if self.strict and warnings:
                print(f"   Warnings (treated as errors in strict mode): {len(warnings)}")

        print()

        # Show errors
        if errors:
            print("Errors:")
            for error in errors:
                print(f"  {error}")
            print()

        # Show warnings
        if warnings:
            severity = "Errors (strict mode)" if self.strict else "Warnings"
            print(f"{severity}:")
            for warning in warnings:
                symbol = "❌" if self.strict else "⚠️ "
                print(f"  {symbol} {warning}")
            print()

        # Record violations
        if not is_valid or (self.strict and warnings):
            self.violations.append({
                "check": "hierarchy_consistency",
                "severity": "error",
                "count": len(errors) + (len(warnings) if self.strict else 0),
                "details": {
                    "errors": errors,
                    "warnings": warnings if self.strict else [],
                },
            })

        total_issues = len(errors) + (len(warnings) if self.strict else 0)
        return (total_issues == 0, total_issues)

    def run(self) -> int:
        """
        Run all CI checks.

        Returns:
            Exit code (0=pass, 1=tag_name fail, 2=hierarchy fail, 3=both fail)
        """
        print()
        print("╔" + "=" * 58 + "╗")
        print("║" + " " * 15 + "CI TAG LINT GUARD" + " " * 26 + "║")
        print("╚" + "=" * 58 + "╝")
        print()

        if self.strict:
            print("⚙️  Mode: STRICT (warnings treated as errors)")
        else:
            print("⚙️  Mode: NORMAL (warnings are non-blocking)")
        print()

        # Run both checks
        tag_name_passed, tag_name_issues = self.run_tag_name_lint()
        hierarchy_passed, hierarchy_issues = self.run_hierarchy_consistency_check()

        # Final summary
        print("=" * 60)
        print("FINAL SUMMARY")
        print("=" * 60)
        print()

        checks = [
            ("Tag Name Lint", tag_name_passed, tag_name_issues),
            ("Hierarchy Consistency", hierarchy_passed, hierarchy_issues),
        ]

        all_passed = all(passed for _, passed, _ in checks)

        for check_name, passed, issues in checks:
            status = "✅ PASS" if passed else f"❌ FAIL ({issues} issue(s))"
            print(f"  {check_name:30} {status}")

        print()

        if all_passed:
            print("🎉 ALL CHECKS PASSED - Ready to merge!")
            return 0
        else:
            print("❌ CHECKS FAILED - Fix violations before merging")

            # Determine exit code
            if not tag_name_passed and not hierarchy_passed:
                return 3  # Both failed
            elif not tag_name_passed:
                return 1  # Tag name failed
            else:
                return 2  # Hierarchy failed


def main():
    """Main entry point for CI tag lint."""
    parser = argparse.ArgumentParser(
        description="CI guard for tag naming and hierarchy consistency",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all checks in normal mode
  python3 scripts/ci_tag_lint.py

  # Run in strict mode (warnings as errors)
  python3 scripts/ci_tag_lint.py --strict

  # Scan specific directory
  python3 scripts/ci_tag_lint.py --path rule_tagger2/detectors
        """,
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors (fails CI on warnings)",
    )

    parser.add_argument(
        "--path",
        type=str,
        default="rule_tagger2",
        help="Directory to scan for tag usage (default: rule_tagger2/)",
    )

    args = parser.parse_args()

    # Run CI checks
    ci_lint = CITagLint(strict=args.strict, scan_path=args.path)
    exit_code = ci_lint.run()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
