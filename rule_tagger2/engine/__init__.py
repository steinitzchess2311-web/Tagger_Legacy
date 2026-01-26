"""
Engine client abstractions for the rule_tagger2 pipeline.
"""

from .protocol import EngineClient
from .stockfish import StockfishEngineClient

__all__ = ["EngineClient", "StockfishEngineClient"]
