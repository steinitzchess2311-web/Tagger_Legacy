"""
Tag assembly helpers for detector outputs.
"""
from __future__ import annotations

from typing import Dict, Iterable, List


def assemble_tags(all_flags: Dict[str, bool], alias_map: Dict[str, str]) -> List[str]:
    """
    Convert boolean tag flags into a deduplicated tag list with alias support.

    `alias_map` remaps legacy tag names (e.g. ``misplaced_maneuver``) to their
    canonical public-facing variants (e.g. ``failed_maneuver``). When an alias
    is applied the original flag name is suppressed to avoid duplicates.
    """
    ordered_flags: Iterable[str] = [tag for tag, active in all_flags.items() if active]
    primary: List[str] = []
    seen: set[str] = set()
    for tag in ordered_flags:
        remapped = alias_map.get(tag, tag)
        if remapped in seen:
            continue
        seen.add(remapped)
        primary.append(remapped)
    return primary
