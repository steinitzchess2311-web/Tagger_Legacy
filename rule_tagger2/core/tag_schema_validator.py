"""
Tag Schema Validator

Validates tag_catalog.yml for:
- Orphan child tags (children without valid parents)
- Circular parent-child relationships
- Duplicate aliases
- Invalid detector references
- Missing required fields
- Type mismatches

Usage:
    python3 -m rule_tagger2.core.tag_schema_validator
    python3 -m rule_tagger2.core.tag_schema_validator --catalog path/to/catalog.yml
    python3 -m rule_tagger2.core.tag_schema_validator --strict
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import yaml


class ValidationError:
    """Represents a validation error"""

    def __init__(self, severity: str, tag: str, message: str):
        self.severity = severity  # "error" or "warning"
        self.tag = tag
        self.message = message

    def __str__(self) -> str:
        emoji = "❌" if self.severity == "error" else "⚠️"
        return f"{emoji} [{self.severity.upper()}] {self.tag}: {self.message}"


class TagSchemaValidator:
    """Validates tag catalog schema and relationships"""

    # Known detector modules/classes
    VALID_DETECTORS = {
        "legacy.core",
        "detectors.tension.TensionDetector",
        "detectors.prophylaxis.ProphylaxisDetector",
        "detectors.cod_v2.ControlOverDynamicsV2Detector",
    }

    # Required fields for each tag
    REQUIRED_FIELDS = {
        "family",
        "parent",
        "children",
        "aliases",
        "deprecated",
        "detector",
        "since_version",
        "priority",
        "description",
        "category",
    }

    def __init__(self, catalog_path: str, strict: bool = False):
        self.catalog_path = catalog_path
        self.strict = strict
        self.catalog: Dict[str, Any] = {}
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []

    def load_catalog(self) -> bool:
        """Load and parse tag_catalog.yml"""
        try:
            with open(self.catalog_path, "r", encoding="utf-8") as f:
                self.catalog = yaml.safe_load(f)

            # Remove schema metadata
            self.catalog.pop("schema_version", None)
            self.catalog.pop("control_schema_version", None)
            return True
        except FileNotFoundError:
            print(f"❌ Error: Catalog file not found: {self.catalog_path}", file=sys.stderr)
            return False
        except yaml.YAMLError as e:
            print(f"❌ Error: Failed to parse YAML: {e}", file=sys.stderr)
            return False

    def validate(self) -> bool:
        """Run all validation checks"""
        self.check_required_fields()
        self.check_orphan_children()
        self.check_circular_relationships()
        self.check_duplicate_aliases()
        self.check_detector_references()
        self.check_priority_values()
        self.check_parent_child_consistency()

        return len(self.errors) == 0

    def check_required_fields(self) -> None:
        """Check that all tags have required fields"""
        for tag_name, tag_meta in self.catalog.items():
            missing_fields = self.REQUIRED_FIELDS - set(tag_meta.keys())
            if missing_fields:
                self.errors.append(
                    ValidationError(
                        "error",
                        tag_name,
                        f"Missing required fields: {', '.join(sorted(missing_fields))}",
                    )
                )

    def check_orphan_children(self) -> None:
        """Check for child tags whose parent doesn't exist or doesn't list them"""
        for tag_name, tag_meta in self.catalog.items():
            parent = tag_meta.get("parent")

            if parent is None:
                continue

            # Check parent exists
            if parent not in self.catalog:
                self.errors.append(
                    ValidationError(
                        "error",
                        tag_name,
                        f"Parent '{parent}' does not exist in catalog",
                    )
                )
                continue

            # Check parent lists this tag as a child
            parent_meta = self.catalog[parent]
            parent_children = parent_meta.get("children", [])

            if tag_name not in parent_children:
                self.errors.append(
                    ValidationError(
                        "error",
                        tag_name,
                        f"Parent '{parent}' does not list '{tag_name}' in its children",
                    )
                )

    def check_circular_relationships(self) -> None:
        """Check for circular parent-child relationships"""
        for tag_name in self.catalog.keys():
            visited = set()
            current = tag_name

            while current is not None:
                if current in visited:
                    cycle = " -> ".join(list(visited) + [current])
                    self.errors.append(
                        ValidationError(
                            "error",
                            tag_name,
                            f"Circular parent relationship detected: {cycle}",
                        )
                    )
                    break

                visited.add(current)
                current = self.catalog.get(current, {}).get("parent")

    def check_duplicate_aliases(self) -> None:
        """Check for duplicate aliases across tags"""
        alias_map: Dict[str, List[str]] = defaultdict(list)

        for tag_name, tag_meta in self.catalog.items():
            aliases = tag_meta.get("aliases", [])
            for alias in aliases:
                alias_map[alias].append(tag_name)

        for alias, tags in alias_map.items():
            if len(tags) > 1:
                self.errors.append(
                    ValidationError(
                        "error",
                        alias,
                        f"Duplicate alias '{alias}' used by: {', '.join(tags)}",
                    )
                )

    def check_detector_references(self) -> None:
        """Check for invalid detector references"""
        for tag_name, tag_meta in self.catalog.items():
            detector = tag_meta.get("detector")

            if not detector:
                continue

            if detector not in self.VALID_DETECTORS:
                severity = "error" if self.strict else "warning"
                msg = f"Unknown detector '{detector}' (not in VALID_DETECTORS)"

                if severity == "error":
                    self.errors.append(ValidationError(severity, tag_name, msg))
                else:
                    self.warnings.append(ValidationError(severity, tag_name, msg))

    def check_priority_values(self) -> None:
        """Check that priority values are valid integers"""
        for tag_name, tag_meta in self.catalog.items():
            priority = tag_meta.get("priority")

            if priority is None:
                continue

            if not isinstance(priority, int):
                self.errors.append(
                    ValidationError(
                        "error",
                        tag_name,
                        f"Priority must be an integer, got {type(priority).__name__}",
                    )
                )
            elif priority < 1:
                self.warnings.append(
                    ValidationError(
                        "warning",
                        tag_name,
                        f"Priority {priority} is less than 1 (unusual)",
                    )
                )

    def check_parent_child_consistency(self) -> None:
        """Check that parent-child relationships are bidirectional"""
        for tag_name, tag_meta in self.catalog.items():
            children = tag_meta.get("children", [])

            for child in children:
                if child not in self.catalog:
                    self.errors.append(
                        ValidationError(
                            "error",
                            tag_name,
                            f"Child '{child}' does not exist in catalog",
                        )
                    )
                    continue

                child_meta = self.catalog[child]
                child_parent = child_meta.get("parent")

                if child_parent != tag_name:
                    self.errors.append(
                        ValidationError(
                            "error",
                            tag_name,
                            f"Child '{child}' has parent='{child_parent}', expected '{tag_name}'",
                        )
                    )

    def print_report(self) -> None:
        """Print validation report"""
        total_errors = len(self.errors)
        total_warnings = len(self.warnings)

        print("=" * 70)
        print("TAG SCHEMA VALIDATION REPORT")
        print("=" * 70)
        print(f"Catalog: {self.catalog_path}")
        print(f"Total tags: {len(self.catalog)}")
        print(f"Errors: {total_errors}")
        print(f"Warnings: {total_warnings}")
        print("=" * 70)

        if self.errors:
            print("")
            print("ERRORS:")
            for error in self.errors:
                print(f"  {error}")

        if self.warnings:
            print("")
            print("WARNINGS:")
            for warning in self.warnings:
                print(f"  {warning}")

        print("")
        if total_errors == 0:
            print("✅ VALIDATION PASSED - No errors found")
        else:
            print(f"❌ VALIDATION FAILED - {total_errors} error(s) found")

        if self.strict and total_warnings > 0:
            print(f"⚠️  STRICT MODE - {total_warnings} warning(s) treated as errors")

        print("=" * 70)

    def get_exit_code(self) -> int:
        """Get exit code based on validation result"""
        if self.errors:
            return 1
        if self.strict and self.warnings:
            return 1
        return 0


def main():
    parser = argparse.ArgumentParser(description="Validate tag_catalog.yml schema")
    parser.add_argument(
        "--catalog",
        default="rule_tagger2/core/tag_catalog.yml",
        help="Path to tag_catalog.yml (default: rule_tagger2/core/tag_catalog.yml)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors (default: False)",
    )
    args = parser.parse_args()

    # Resolve path
    if Path(args.catalog).is_absolute():
        catalog_path = args.catalog
    else:
        # Assume relative to repo root (parent of script)
        script_dir = Path(__file__).parent
        repo_root = script_dir.parent.parent
        catalog_path = str(repo_root / args.catalog)

    validator = TagSchemaValidator(catalog_path, strict=args.strict)

    if not validator.load_catalog():
        sys.exit(1)

    validator.validate()
    validator.print_report()

    sys.exit(validator.get_exit_code())


if __name__ == "__main__":
    main()
