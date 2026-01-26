"""Manual sanity checks for CoD subtype detectors.

These tests operate on the detector helpers directly to avoid the expense of
running engine analysis. They focus on high-signal scenarios that should remain
stable across refactors.
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

import chess
from rule_tagger2.core.engine_io import contact_profile, material_balance

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from rule_tagger2.legacy.core import (
    CONTROL,
    detect_cod_plan_kill,
    detect_cod_simplify,
    detect_cod_slowdown,
    detect_cod_space_clamp,
    select_cod_subtype,
)


def _base_ctx() -> dict:
    return {
        "allow_positional": True,
        "has_dynamic_in_band": True,
        "played_kind": "positional",
        "eval_drop_cp": 0,
        "strict_mode": False,
        "captures_this_ply": 0,
        "square_defended_by_opp": 0,
        "square_defended_by_self": 0,
        "has_immediate_tactical_followup": False,
        "volatility_drop_cp": 30.0,
        "vol_drop_cp": 30.0,
        "opp_mobility_drop": 5.0,
        "op_mob_drop": 5.0,
        "tension_delta": -1.5,
        "phase": "MID",
        "phase_bucket": "middlegame",
        "phase_ratio": 0.5,
        "current_ply": 20,
        "cooldown_plies": CONTROL.get("COOLDOWN_PLIES", 3),
        "active_piece_drop": 0,
        "own_active_drop": 0,
        "opp_active_drop": 0,
        "op_active_drop": 0,
        "total_active_drop": 0,
        "material_delta_self": 0.0,
        "material_delta_self_cp": 0,
        "captured_value_cp": 0,
        "exchange_count": 0,
    }


def _active_non_pawn_count(board: chess.Board, color: chess.Color) -> int:
    return sum(
        1
        for square in chess.SquareSet(board.occupied_co[color])
        if (piece := board.piece_at(square)) and piece.piece_type not in (chess.KING, chess.PAWN)
    )


def _contact_total(board: chess.Board, color: chess.Color) -> int:
    probe = board.copy(stack=False)
    probe.turn = color
    _, _, capture_moves, checking_moves = contact_profile(probe)
    return capture_moves + checking_moves


class ManualCoDDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = copy.deepcopy(CONTROL)

    def test_simplify_detector_passes_on_heavy_exchange(self) -> None:
        ctx = _base_ctx()
        ctx.update(
            {
                "is_capture": True,
                "captured_piece_type": chess.QUEEN,
                "captures_this_ply": 1,
                "square_defended_by_opp": 2,
                "active_piece_drop": 1,
                "total_active_drop": 1,
                "opp_active_drop": 1,
                "material_delta_self": 9.0,
                "material_delta_self_cp": 900,
                "captured_value_cp": 900,
            }
        )
        candidate, gate = detect_cod_simplify(ctx, self.cfg)
        self.assertIsNotNone(candidate)
        self.assertTrue(gate.get("passed"))
        self.assertEqual(candidate["name"], "simplify")
        self.assertEqual(gate.get("expected_recapture_pairs"), 1)

    def test_plan_kill_recognises_plan_drop(self) -> None:
        ctx = _base_ctx()
        ctx.update(
            {
                "plan_drop_passed": True,
                "preventive_score": 0.12,
                "threat_delta": 0.4,
            }
        )
        candidate, gate = detect_cod_plan_kill(ctx, self.cfg)
        self.assertIsNotNone(candidate)
        self.assertTrue(gate.get("passed"))
        self.assertEqual(candidate["name"], "plan_kill")

    def test_slowdown_requires_dynamic_band(self) -> None:
        ctx = _base_ctx()
        ctx["eval_drop_cp"] = self.cfg.get("EVAL_DROP_CP", 20)
        ctx["volatility_drop_cp"] = self.cfg.get("VOLATILITY_DROP_CP", 12) + 5
        ctx["vol_drop_cp"] = ctx["volatility_drop_cp"]
        ctx["opp_mobility_drop"] = (
            self.cfg.get("OP_MOBILITY_DROP", 2)
            + self.cfg.get("PHASE_ADJUST", {}).get("MID", {}).get("OP_MOB_DROP", 0)
            + 1
        )
        ctx["op_mob_drop"] = ctx["opp_mobility_drop"]
        candidate, gate = detect_cod_slowdown(ctx, self.cfg)
        self.assertIsNotNone(candidate)
        self.assertTrue(gate.get("passed"))
        self.assertEqual(candidate["name"], "slowdown")

    def test_cooldown_suppresses_recent_subtype(self) -> None:
        ctx = _base_ctx()
        ctx.update(
            {
                "is_capture": True,
                "captured_piece_type": chess.ROOK,
                "captures_this_ply": 1,
                "square_defended_by_opp": 1,
                "active_piece_drop": 1,
                "total_active_drop": 1,
                "opp_active_drop": 1,
                "material_delta_self": 5.0,
                "material_delta_self_cp": 500,
                "captured_value_cp": 500,
                "has_immediate_tactical_followup": False,
                "exchange_count": 1,
                "has_dynamic_in_band": False,
            }
        )
        last_state = {"kind": "simplify", "ply": ctx["current_ply"] - 1}
        selected, suppressed, cooldown_remaining, gate_log, detected = select_cod_subtype(
            ctx,
            self.cfg,
            last_state,
        )
        self.assertIsNone(selected)
        self.assertIn("simplify", suppressed)
        self.assertGreater(cooldown_remaining, 0)
        self.assertTrue(gate_log["simplify"]["passed"])

    def test_space_clamp_not_triggered_without_space_gain(self) -> None:
        ctx = _base_ctx()
        ctx.update(
            {
                "space_gain": 0.01,
            }
        )
        candidate, gate = detect_cod_space_clamp(ctx, self.cfg)
        self.assertIsNone(candidate)
        self.assertFalse(gate.get("passed"))

    def test_simplify_expected_recapture_from_fen(self) -> None:
        fen = "r2r2k1/2q5/8/8/8/8/2Q3PP/3R1RK1 w - - 0 1"
        board = chess.Board(fen)
        move = chess.Move.from_uci("d1d8")
        self.assertTrue(board.is_capture(move))

        played_board = board.copy(stack=False)
        played_board.push(move)

        material_before = material_balance(board, chess.WHITE)
        material_after = material_balance(played_board, chess.WHITE)
        material_delta_self = round(material_after - material_before, 3)
        material_delta_self_cp = int(round(material_delta_self * 100))

        total_active_before = _active_non_pawn_count(board, chess.WHITE) + _active_non_pawn_count(board, chess.BLACK)
        total_active_after = _active_non_pawn_count(played_board, chess.WHITE) + _active_non_pawn_count(played_board, chess.BLACK)
        total_active_drop = max(0, total_active_before - total_active_after)
        own_active_drop = max(0, _active_non_pawn_count(board, chess.WHITE) - _active_non_pawn_count(played_board, chess.WHITE))
        opp_active_drop = max(0, _active_non_pawn_count(board, chess.BLACK) - _active_non_pawn_count(played_board, chess.BLACK))

        tension_before = _contact_total(board, chess.WHITE) + _contact_total(board, chess.BLACK)
        tension_after = _contact_total(played_board, chess.WHITE) + _contact_total(played_board, chess.BLACK)
        tension_delta = tension_after - tension_before
        if tension_delta > -0.5:
            tension_delta = -1.0

        probe_before = board.copy(stack=False)
        probe_before.turn = chess.BLACK
        opp_mobility_before = sum(1 for _ in probe_before.legal_moves)
        opp_mobility_after = sum(1 for _ in played_board.legal_moves)
        opp_mob_drop = max(2, opp_mobility_before - opp_mobility_after)

        ctx = _base_ctx()
        ctx.update(
            {
                "allow_positional": True,
                "phase": "MID",
                "phase_bucket": "middlegame",
                "is_capture": True,
                "captured_piece_type": chess.ROOK,
                "captures_this_ply": 1,
                "square_defended_by_opp": len(played_board.attackers(chess.BLACK, move.to_square)),
                "square_defended_by_self": len(played_board.attackers(chess.WHITE, move.to_square)),
                "total_active_drop": total_active_drop,
                "active_piece_drop": total_active_drop,
                "own_active_drop": own_active_drop,
                "opp_active_drop": opp_active_drop,
                "op_active_drop": opp_active_drop,
                "material_delta_self": material_delta_self,
                "material_delta_self_cp": material_delta_self_cp,
                "captured_value_cp": 500,
                "volatility_drop_cp": 22.0,
                "vol_drop_cp": 22.0,
                "tension_delta": tension_delta,
                "opp_mobility_drop": opp_mob_drop,
                "op_mob_drop": opp_mob_drop,
                "exchange_count": max(1, total_active_drop),
                "has_immediate_tactical_followup": False,
                "has_dynamic_in_band": True,
            }
        )

        candidate, gate = detect_cod_simplify(ctx, self.cfg)
        self.assertIsNotNone(candidate)
        self.assertTrue(gate.get("passed"))
        self.assertEqual(candidate["name"], "simplify")
        self.assertGreaterEqual(gate.get("square_defended_by_opp", 0), 1)
        self.assertEqual(candidate["metrics"]["exchange_pairs"], min(2, ctx["captures_this_ply"] + 1))


if __name__ == "__main__":
    unittest.main()
