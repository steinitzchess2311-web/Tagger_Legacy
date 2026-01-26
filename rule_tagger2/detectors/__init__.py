"""
Tag detector modules for modular tag detection.
"""
from .base import DetectorMetadata, TagDetector
from .knight_bishop_exchange import KnightBishopExchangeDetector
from .tension import TensionDetector

__all__ = [
    "TagDetector",
    "DetectorMetadata",
    "TensionDetector",
    "KnightBishopExchangeDetector",
]
