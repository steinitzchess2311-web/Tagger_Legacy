"""
Configuration for Control over Dynamics v2.

This module reads thresholds from metrics_thresholds.yml WITHOUT modifying it.
All values are read-only and cached.
"""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


@dataclass
class CoDThresholds:
    """
    Thresholds for CoD detection.

    These are READ from metrics_thresholds.yml, not written.
    """

    # Tactical gating
    tactical_weight_ceiling: float = 0.65
    mate_threat_gate: bool = True
    blunder_threat_thresh: float = 0.8

    # Volatility
    volatility_drop_cp: float = 80.0

    # Mobility
    opp_mobility_drop: float = 0.15

    # Evaluation
    eval_drop: float = 0.5

    # King safety
    king_safety_thresh: float = 0.15
    king_safety_tolerance: float = 0.05

    # Tension
    tension_delta_mid: float = 0.3
    tension_delta_end: float = 0.15

    # Simplification
    simplify_min_exchange: float = 3.0

    # Cooldown
    cooldown_plies: int = 4

    # Prophylaxis
    preventive_trigger: float = 0.25
    threat_drop_min: float = 0.2

    @classmethod
    def from_yaml(cls, yaml_path: Optional[Path] = None) -> "CoDThresholds":
        """
        Load thresholds from YAML file.

        Args:
            yaml_path: Path to metrics_thresholds.yml. If None, searches for it.

        Returns:
            CoDThresholds instance with loaded values
        """
        if yaml_path is None:
            # Search for metrics_thresholds.yml in common locations
            candidates = [
                Path("metrics_thresholds.yml"),
                Path("config/metrics_thresholds.yml"),
                Path("../metrics_thresholds.yml"),
            ]
            for candidate in candidates:
                if candidate.exists():
                    yaml_path = candidate
                    break

        if yaml_path is None or not yaml_path.exists():
            # Return defaults if file not found
            return cls()

        with open(yaml_path) as f:
            data = yaml.safe_load(f) or {}

        # Extract CoD-related thresholds
        control = data.get("control_over_dynamics", {})
        prophylaxis = data.get("prophylaxis", {})

        return cls(
            tactical_weight_ceiling=control.get(
                "tactical_weight_ceiling", cls.tactical_weight_ceiling
            ),
            volatility_drop_cp=control.get("volatility_drop_cp", cls.volatility_drop_cp),
            opp_mobility_drop=control.get("opp_mobility_drop", cls.opp_mobility_drop),
            eval_drop=control.get("eval_drop", cls.eval_drop),
            king_safety_thresh=control.get("king_safety_thresh", cls.king_safety_thresh),
            king_safety_tolerance=control.get(
                "king_safety_tolerance", cls.king_safety_tolerance
            ),
            simplify_min_exchange=control.get(
                "simplify_min_exchange", cls.simplify_min_exchange
            ),
            cooldown_plies=control.get("cooldown_plies", cls.cooldown_plies),
            preventive_trigger=prophylaxis.get("preventive_trigger", cls.preventive_trigger),
            threat_drop_min=prophylaxis.get("threat_drop_min", cls.threat_drop_min),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tactical_weight_ceiling": self.tactical_weight_ceiling,
            "volatility_drop_cp": self.volatility_drop_cp,
            "opp_mobility_drop": self.opp_mobility_drop,
            "eval_drop": self.eval_drop,
            "king_safety_thresh": self.king_safety_thresh,
            "king_safety_tolerance": self.king_safety_tolerance,
            "tension_delta_mid": self.tension_delta_mid,
            "tension_delta_end": self.tension_delta_end,
            "simplify_min_exchange": self.simplify_min_exchange,
            "cooldown_plies": self.cooldown_plies,
            "preventive_trigger": self.preventive_trigger,
            "threat_drop_min": self.threat_drop_min,
        }


def is_cod_v2_enabled() -> bool:
    """
    Check if CoD v2 is enabled via environment variable.

    Returns:
        True if CLAUDE_COD_V2=1, False otherwise
    """
    return os.environ.get("CLAUDE_COD_V2", "0") == "1"


def get_thresholds() -> CoDThresholds:
    """
    Get CoD thresholds.

    This function caches the result for performance.

    Returns:
        CoDThresholds instance
    """
    if not hasattr(get_thresholds, "_cache"):
        get_thresholds._cache = CoDThresholds.from_yaml()
    return get_thresholds._cache
