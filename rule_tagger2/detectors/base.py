"""
Base class for all tag detectors.

This module defines the interface that all tag detectors must implement.
Each detector is responsible for analyzing a specific aspect of a chess move
(e.g., tension, prophylaxis, tactical themes) and returning relevant tags.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DetectorMetadata:
    """Metadata returned by a detector after analysis."""

    detector_name: str
    tags_found: List[str] = field(default_factory=list)
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    diagnostic_info: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: Optional[float] = None


class TagDetector(ABC):
    """
    Abstract base class for all tag detectors.

    Each detector should:
    1. Analyze a specific aspect of the position/move
    2. Return a list of relevant tags
    3. Provide metadata about the detection process
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Returns the unique name of this detector.

        Example: "Tension", "Prophylaxis", "Tactical"
        """
        pass

    @abstractmethod
    def detect(self, context: 'AnalysisContext') -> List[str]:
        """
        Analyzes the position and returns detected tags.

        Args:
            context: AnalysisContext containing board state, metrics, and analysis data

        Returns:
            List of tag strings (e.g., ["tension_creation_immediate", "initiative_boost"])
        """
        pass

    @abstractmethod
    def get_metadata(self) -> DetectorMetadata:
        """
        Returns metadata about the most recent detection.

        Returns:
            DetectorMetadata with diagnostic information
        """
        pass

    def is_applicable(self, context: 'AnalysisContext') -> bool:
        """
        Determines if this detector should run for the given context.

        Override this to skip detection based on game phase, position type, etc.

        Args:
            context: AnalysisContext to check

        Returns:
            True if detector should run, False to skip
        """
        return True

    def get_priority(self) -> int:
        """
        Returns execution priority (lower number = higher priority).

        Detectors run in priority order. Tactical detectors might run first,
        positional detectors later.

        Returns:
            Integer priority (0-100, default 50)
        """
        return 50
