"""
Shared board constants used by the ChessEvaluator components.
"""
from __future__ import annotations

import chess

CENTER_SQUARES = [
    chess.D4,
    chess.E4,
    chess.D5,
    chess.E5,
]

EXTENDED_CENTER = [
    chess.C3,
    chess.D3,
    chess.E3,
    chess.F3,
    chess.C4,
    chess.D4,
    chess.E4,
    chess.F4,
    chess.C5,
    chess.D5,
    chess.E5,
    chess.F5,
    chess.C6,
    chess.D6,
    chess.E6,
    chess.F6,
]

MOBILITY_BONUS = {
    chess.KNIGHT: [-62, -53, -12, 0, 12, 29, 44, 53, 63],
    chess.BISHOP: [-49, -24, -10, 0, 14, 29, 42, 55, 63, 70, 77, 84, 91, 96],
    chess.ROOK: [-58, -27, -15, -5, 4, 13, 22, 31, 39, 46, 53, 60, 67, 73, 79],
    chess.QUEEN: [
        -39,
        -21,
        -7,
        7,
        21,
        36,
        50,
        62,
        74,
        86,
        98,
        110,
        122,
        134,
        146,
        158,
        170,
        182,
        194,
        206,
        218,
        230,
        242,
        254,
        266,
        278,
        290,
        302,
    ],
}

__all__ = ["CENTER_SQUARES", "EXTENDED_CENTER", "MOBILITY_BONUS"]
