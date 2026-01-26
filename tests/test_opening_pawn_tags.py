import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PACKAGE_ROOT = ROOT / "rule_tagger_lichessbot"
if PACKAGE_ROOT.is_dir() and str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from rule_tagger_lichessbot.rule_tagger2.legacy.core import _attach_persistent_opening_tags
from rule_tagger_lichessbot.rule_tagger2.legacy.opening_pawns import detect_opening_pawn_tags, MIN_PIECES_FOR_OPENING
import chess


def test_opening_tags_added_when_gating_passes():
    raw_tags = ["tension_creation"]
    gated_tags = ["tension_creation"]
    persistent = ["opening_central_pawn_move"]

    raw_result, gated_result = _attach_persistent_opening_tags(
        raw_tags.copy(), gated_tags.copy(), persistent
    )

    assert "opening_central_pawn_move" in raw_result
    assert "opening_central_pawn_move" in gated_result


def test_opening_tags_preserved_when_gating_overrides():
    raw_tags = ["missed_tactic"]
    gated_tags = ["prophylactic_meaningless"]
    persistent = ["opening_rook_pawn_move"]

    raw_result, gated_result = _attach_persistent_opening_tags(
        raw_tags.copy(), gated_tags.copy(), persistent
    )

    assert "opening_rook_pawn_move" in raw_result
    assert "opening_rook_pawn_move" in gated_result
    # Ensure non-opening gating tags are retained
    assert "prophylactic_meaningless" in gated_result


def test_detect_opening_pawn_tags_allows_light_trades():
    # Remove two minor pieces but keep early fullmove; still count as opening
    fen = "rnbqkb1r/pppppppp/5n2/8/2PP4/8/PP2PPPP/RNBQKB1R b KQkq - 0 2"
    board = chess.Board(fen)
    move = chess.Move.from_uci("d7d5")
    is_central, is_rook, tags = detect_opening_pawn_tags(board, move)
    assert is_central
    assert not is_rook
    assert "opening_central_pawn_move" in tags
