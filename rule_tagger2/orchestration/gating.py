"""
Tag gating and filtering logic.

This module handles:
1. Tactical weight gating (suppress positional tags in tactical positions)
2. Priority-based conflict resolution
3. Cooldown mechanism (prevent repeated tags)
4. Tag suppression tracking

Current Status: P1 - Passthrough skeleton
"""
from typing import Dict, List, Optional, Tuple


class TagGate:
    """
    Applies gating rules to filter and prioritize tags.

    Gating Rules:
    1. Tactical Gate: Suppress positional tags when tactical_weight > threshold
    2. Priority Gate: When multiple tags conflict, keep highest priority
    3. Cooldown Gate: Prevent same tag family within N plies
    4. Mate Threat Gate: Suppress certain tags in mate threats
    """

    def __init__(self):
        """Initialize gating system."""
        # Will be populated from config in P2+
        self.tactical_threshold = 0.65
        self.cooldown_plies = 4
        self.cooldown_state: Dict[str, int] = {}  # tag_family -> last_ply

    def apply_gates(
        self,
        tags: List[str],
        tactical_weight: float,
        current_ply: int,
        mate_threat: bool = False,
        priority_order: Optional[List[str]] = None,
    ) -> Tuple[List[str], Dict[str, any]]:
        """
        Apply all gating rules to the tag list.

        Args:
            tags: List of detected tags
            tactical_weight: Tactical weight of position
            current_ply: Current ply number
            mate_threat: Whether there's a mate threat
            priority_order: Optional custom priority order

        Returns:
            (filtered_tags, gate_diagnostic)
        """
        # P1: Passthrough (no filtering)
        diagnostic = {
            "tactical_weight": tactical_weight,
            "current_ply": current_ply,
            "mate_threat": mate_threat,
            "gates_applied": [],
            "tags_suppressed": [],
            "reason": "P1 passthrough - no gating yet",
        }

        return tags, diagnostic

    def apply_tactical_gate(
        self,
        tags: List[str],
        tactical_weight: float
    ) -> Tuple[List[str], List[str]]:
        """
        Apply tactical weight gating.

        Suppresses positional tags when position is highly tactical.

        Args:
            tags: Input tags
            tactical_weight: Tactical weight (0-1)

        Returns:
            (kept_tags, suppressed_tags)
        """
        # P1: Passthrough
        # P2+: Implement actual filtering
        return tags, []

    def apply_priority_gate(
        self,
        tags: List[str],
        priority_order: Optional[List[str]] = None
    ) -> Tuple[List[str], List[str]]:
        """
        Apply priority-based filtering for conflicting tags.

        Args:
            tags: Input tags
            priority_order: Optional custom priority order

        Returns:
            (kept_tags, suppressed_tags)
        """
        # P1: Passthrough
        return tags, []

    def apply_cooldown_gate(
        self,
        tags: List[str],
        current_ply: int
    ) -> Tuple[List[str], List[str]]:
        """
        Apply cooldown filtering.

        Prevents same tag family from appearing too frequently.

        Args:
            tags: Input tags
            current_ply: Current ply number

        Returns:
            (kept_tags, suppressed_tags)
        """
        # P1: Passthrough
        return tags, []

    def update_cooldown_state(self, tags: List[str], current_ply: int):
        """
        Update cooldown state after tags are emitted.

        Args:
            tags: Tags that were emitted
            current_ply: Current ply number
        """
        # P2+: Track tag families
        pass


def apply_gating(
    tags: List[str],
    tactical_weight: float = 0.0,
    current_ply: int = 0,
    **kwargs
) -> List[str]:
    """
    Convenience function to apply gating.

    Args:
        tags: List of tags to filter
        tactical_weight: Tactical weight
        current_ply: Current ply
        **kwargs: Additional gating parameters

    Returns:
        Filtered tag list
    """
    gate = TagGate()
    filtered, _ = gate.apply_gates(
        tags=tags,
        tactical_weight=tactical_weight,
        current_ply=current_ply,
        **kwargs
    )
    return filtered
