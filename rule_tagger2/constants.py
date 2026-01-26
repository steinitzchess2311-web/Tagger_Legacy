"""
Central constants module for rule_tagger2.

This module provides ORDERED_TAGS, the canonical tag ordering derived
from TAG_PRIORITY in models.py. Use this for consistent tag serialization,
telemetry export, and dashboard rendering.
"""

from rule_tagger2.models import TAG_PRIORITY

# Derive ORDERED_TAGS from TAG_PRIORITY (sorted by priority, then alphabetically)
ORDERED_TAGS = sorted(TAG_PRIORITY.keys(), key=lambda tag: (TAG_PRIORITY[tag], tag))

__all__ = ["ORDERED_TAGS"]
