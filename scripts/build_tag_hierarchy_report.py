#!/usr/bin/env python3
"""
Build Tag Hierarchy Report

Reads tag_catalog.yml and generates:
1. reports/tags_hierarchy.md (human-readable markdown with collapsible tree)
2. reports/tags_hierarchy.json (machine-readable JSON)

Usage:
    python3 scripts/build_tag_hierarchy_report.py
    python3 scripts/build_tag_hierarchy_report.py --catalog path/to/catalog.yml
    python3 scripts/build_tag_hierarchy_report.py --output-dir custom/output
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml


class TagHierarchyBuilder:
    """Builds tag hierarchy reports from tag_catalog.yml"""

    def __init__(self, catalog_path: str):
        self.catalog_path = catalog_path
        self.catalog: Dict[str, Any] = {}
        self.families: Dict[str, List[str]] = defaultdict(list)
        self.parents: Dict[str, List[str]] = defaultdict(list)
        self.orphans: Set[str] = set()
        self.deprecated: List[str] = []

    def load_catalog(self) -> None:
        """Load and parse tag_catalog.yml"""
        with open(self.catalog_path, "r", encoding="utf-8") as f:
            self.catalog = yaml.safe_load(f)

        # Remove schema metadata
        self.catalog.pop("schema_version", None)
        self.catalog.pop("control_schema_version", None)

    def analyze_relationships(self) -> None:
        """Analyze tag relationships: families, parents, orphans"""
        for tag_name, tag_meta in self.catalog.items():
            # Group by family
            family = tag_meta.get("family")
            if family:
                self.families[family].append(tag_name)

            # Track parent-child relationships
            parent = tag_meta.get("parent")
            if parent:
                self.parents[parent].append(tag_name)
            elif not tag_meta.get("children"):
                # Potential orphan: no parent and no children
                if family not in ["meta", "structural"]:  # Meta tags can be standalone
                    self.orphans.add(tag_name)

            # Track deprecated tags
            if tag_meta.get("deprecated", False):
                self.deprecated.append(tag_name)

    def build_markdown_report(self) -> str:
        """Generate human-readable markdown report"""
        lines = [
            "# Tag Hierarchy Report",
            "",
            f"**Generated from:** `{self.catalog_path}`",
            f"**Total tags:** {len(self.catalog)}",
            f"**Families:** {len(self.families)}",
            f"**Deprecated tags:** {len(self.deprecated)}",
            "",
            "---",
            "",
        ]

        # Table of Contents
        lines.extend([
            "## Table of Contents",
            "",
        ])
        for family in sorted(self.families.keys()):
            lines.append(f"- [{family.title()}](#{family.lower()})")
        lines.extend(["", "---", ""])

        # Family sections
        for family in sorted(self.families.keys()):
            lines.extend(self._build_family_section(family))

        # Deprecated section
        if self.deprecated:
            lines.extend([
                "---",
                "",
                "## Deprecated Tags",
                "",
            ])
            for tag in sorted(self.deprecated):
                tag_meta = self.catalog[tag]
                lines.append(f"- **{tag}** (deprecated since v{tag_meta.get('since_version', 'unknown')})")
            lines.append("")

        # Orphans warning
        if self.orphans:
            lines.extend([
                "---",
                "",
                "## ⚠️ Potential Orphan Tags",
                "",
                "_Tags without parent or children (excluding meta/structural families)_",
                "",
            ])
            for tag in sorted(self.orphans):
                lines.append(f"- **{tag}**")
            lines.append("")

        return "\n".join(lines)

    def _build_family_section(self, family: str) -> List[str]:
        """Build markdown section for one family"""
        lines = [
            f"## {family.title()}",
            "",
        ]

        tags = sorted(self.families[family], key=lambda t: self.catalog[t].get("priority", 999))

        # Group by parent
        parent_groups: Dict[Optional[str], List[str]] = defaultdict(list)
        for tag in tags:
            parent = self.catalog[tag].get("parent")
            parent_groups[parent].append(tag)

        # Render parent-less tags first
        if None in parent_groups:
            for tag in parent_groups[None]:
                lines.extend(self._build_tag_entry(tag, level=0))

        # Render children under parents
        parent_keys = [p for p in parent_groups.keys() if p is not None]
        for parent in sorted(parent_keys):
            # Parent already rendered above, render children
            for child in sorted(parent_groups[parent], key=lambda t: self.catalog[t].get("priority", 999)):
                lines.extend(self._build_tag_entry(child, level=1, parent=parent))

        lines.append("")
        return lines

    def _build_tag_entry(self, tag: str, level: int = 0, parent: Optional[str] = None) -> List[str]:
        """Build markdown entry for a single tag with detector, thresholds, and A/B switch info"""
        tag_meta = self.catalog[tag]
        indent = "  " * level

        lines = [f"{indent}<details>"]

        # Summary line with enhanced badges
        summary_parts = [f"**{tag}**"]
        if parent:
            summary_parts.append(f"_(child of {parent})_")
        if tag_meta.get("deprecated"):
            summary_parts.append("⚠️ DEPRECATED")

        priority = tag_meta.get("priority", "N/A")
        summary_parts.append(f"[priority: {priority}]")

        # Add detector badge
        detector = tag_meta.get("detector", "N/A")
        if "TensionDetector" in detector:
            summary_parts.append("🔵 TensionV2")
        elif "ProphylaxisDetector" in detector:
            summary_parts.append("🟢 Prophylaxis")
        elif "ControlOverDynamics" in detector:
            summary_parts.append("🟣 CoDV2")
        elif detector == "legacy.core":
            summary_parts.append("⚪ Legacy")

        lines.append(f"{indent}<summary>{' '.join(summary_parts)}</summary>")
        lines.append("")

        # Details
        lines.append(f"{indent}- **Description:** {tag_meta.get('description', 'N/A')}")
        lines.append(f"{indent}- **Detector:** `{detector}`")
        lines.append(f"{indent}- **Since:** v{tag_meta.get('since_version', 'unknown')}")

        # A/B Switch Info
        ab_switch = self._get_ab_switch_info(tag, detector)
        if ab_switch:
            lines.append(f"{indent}- **A/B Switch:** {ab_switch}")

        # Key Thresholds
        thresholds = self._get_key_thresholds(tag, tag_meta)
        if thresholds:
            lines.append(f"{indent}- **Key Thresholds:**")
            for threshold_name, threshold_value in thresholds.items():
                lines.append(f"{indent}  - `{threshold_name}`: {threshold_value}")

        # Aliases
        aliases = tag_meta.get("aliases", [])
        if aliases:
            lines.append(f"{indent}- **Aliases:** {', '.join(aliases)}")

        # Children
        children = tag_meta.get("children", [])
        if children:
            lines.append(f"{indent}- **Children ({len(children)}):** {', '.join(children)}")

        # Subtype
        if tag_meta.get("subtype"):
            lines.append(f"{indent}- **Subtype:** `{tag_meta['subtype']}`")

        # A/B switch
        if tag_meta.get("ab_switch"):
            lines.append(f"{indent}- **A/B Switch:** `{tag_meta['ab_switch']}`")

        # Thresholds
        thresholds = tag_meta.get("thresholds", {})
        if thresholds:
            lines.append(f"{indent}- **Thresholds:**")
            for key, value in sorted(thresholds.items()):
                lines.append(f"{indent}  - `{key}`: {value}")

        lines.append(f"{indent}</details>")
        lines.append("")
        return lines

    def _get_ab_switch_info(self, tag: str, detector: str) -> Optional[str]:
        """Get A/B switch information for a tag"""
        # Map detector to A/B switch
        if "TensionDetector" in detector:
            return "`USE_NEW_TENSION=1` (default: 0 = legacy)"
        elif "ControlOverDynamicsV2" in detector:
            return "`USE_NEW_COD=1` (default: 0 = ProphylaxisDetector)"
        # Check for explicit ab_switch in metadata
        tag_meta = self.catalog[tag]
        if tag_meta.get("ab_switch"):
            return f"`{tag_meta['ab_switch']}`"
        return None

    def _get_key_thresholds(self, tag: str, tag_meta: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key thresholds for a tag"""
        thresholds = {}

        # Check explicit thresholds in metadata
        if tag_meta.get("thresholds"):
            return tag_meta["thresholds"]

        # Extract thresholds based on tag family/detector
        family = tag_meta.get("family")
        detector = tag_meta.get("detector", "")

        # Tension family thresholds
        if family == "tension" or "TensionDetector" in detector:
            if "neutral" in tag:
                thresholds = {
                    "min_mobility_evidence": 0.10,
                    "min_contact_evidence": 0.01,
                }
            elif "tension_creation" in tag:
                thresholds = {
                    "min_score_gap": 15,
                    "min_mobility_delta": 0.05,
                }

        # Control family thresholds
        elif family == "control" or "Control" in detector:
            if "simplif" in tag:
                thresholds = {
                    "min_material_delta": -1.5,
                    "min_complexity_reduction": 0.15,
                }
            elif "prophylax" in tag:
                thresholds = {
                    "min_preventive_score": 0.40,
                    "opponent_threat_threshold": 0.30,
                }

        # Maneuver family thresholds
        elif family == "maneuver":
            thresholds = {
                "eval_tolerance": 0.12,
                "min_position_improvement": 0.05,
            }

        # Sacrifice family thresholds
        elif family == "sacrifice":
            if "tactical" in tag:
                thresholds = {
                    "min_eval_recovery": 100,  # cp
                    "max_sacrifice_depth": 3,
                }
            elif "positional" in tag:
                thresholds = {
                    "min_compensation": 50,  # cp
                    "horizon_depth": 10,
                }

        return thresholds

    def build_json_report(self) -> Dict[str, Any]:
        """Generate machine-readable JSON report"""
        report = {
            "metadata": {
                "source": self.catalog_path,
                "total_tags": len(self.catalog),
                "total_families": len(self.families),
                "deprecated_count": len(self.deprecated),
                "orphan_count": len(self.orphans),
            },
            "families": {},
            "tags": {},
            "relationships": {
                "parent_child": {},
                "aliases": {},
            },
            "deprecated": self.deprecated,
            "orphans": list(self.orphans),
        }

        # Family summaries
        for family, tags in self.families.items():
            report["families"][family] = {
                "count": len(tags),
                "tags": sorted(tags),
            }

        # Full tag details
        for tag_name, tag_meta in self.catalog.items():
            report["tags"][tag_name] = tag_meta

        # Relationships
        for parent, children in self.parents.items():
            report["relationships"]["parent_child"][parent] = sorted(children)

        for tag_name, tag_meta in self.catalog.items():
            aliases = tag_meta.get("aliases", [])
            if aliases:
                report["relationships"]["aliases"][tag_name] = aliases

        return report

    def generate_reports(self, output_dir: str) -> None:
        """Generate both markdown and JSON reports"""
        os.makedirs(output_dir, exist_ok=True)

        md_path = os.path.join(output_dir, "tags_hierarchy.md")
        json_path = os.path.join(output_dir, "tags_hierarchy.json")

        # Generate markdown
        md_content = self.build_markdown_report()
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"✅ Markdown report written to: {md_path}")

        # Generate JSON
        json_content = self.build_json_report()
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_content, f, indent=2, ensure_ascii=False)
        print(f"✅ JSON report written to: {json_path}")

        # Print summary
        print("")
        print("=" * 60)
        print("TAG HIERARCHY SUMMARY")
        print("=" * 60)
        print(f"Total tags:       {len(self.catalog)}")
        print(f"Families:         {len(self.families)}")
        print(f"Deprecated tags:  {len(self.deprecated)}")
        print(f"Orphan tags:      {len(self.orphans)}")
        print("")
        print("Families breakdown:")
        for family in sorted(self.families.keys()):
            count = len(self.families[family])
            print(f"  - {family:20s}: {count:3d} tags")
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Build tag hierarchy reports from tag_catalog.yml")
    parser.add_argument(
        "--catalog",
        default="rule_tagger2/core/tag_catalog.yml",
        help="Path to tag_catalog.yml (default: rule_tagger2/core/tag_catalog.yml)",
    )
    parser.add_argument(
        "--output-dir",
        default="reports",
        help="Output directory for reports (default: reports/)",
    )
    args = parser.parse_args()

    # Resolve paths
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    catalog_path = repo_root / args.catalog
    output_dir = repo_root / args.output_dir

    if not catalog_path.exists():
        print(f"❌ Error: Catalog file not found: {catalog_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Building tag hierarchy reports...")
    print(f"Catalog: {catalog_path}")
    print(f"Output:  {output_dir}")
    print("")

    builder = TagHierarchyBuilder(str(catalog_path))
    builder.load_catalog()
    builder.analyze_relationships()
    builder.generate_reports(str(output_dir))


if __name__ == "__main__":
    main()
