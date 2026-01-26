"""
Mock engine for deterministic integration testing without Stockfish dependency.

Provides canned evaluation responses for specific positions to enable
CI-friendly tests that verify detector integration without real engine calls.
"""
from typing import Dict, List, Optional
import chess
import chess.engine


class MockEngine:
    """
    Mock Stockfish-compatible engine that returns pre-recorded evaluations.

    Usage:
        engine = MockEngine()
        info = engine.analyse(board, chess.engine.Limit(depth=20))
        # Returns: {"score": PovScore(...), "pv": [...]}
    """

    def __init__(self):
        # Pre-recorded evaluations for test positions
        # Key: FEN of position BEFORE the move
        # Value: eval data including before/after scores and recapture options
        # IMPORTANT: All scores are from WHITE's perspective (to match legacy analysis.py expectations)
        self._evaluations: Dict[str, Dict] = {
            # Test 1: accurate KBE - Black Nxd2 (~7cp loss)
            # Scores are from WHITE's perspective
            "r1b2rk1/p5b1/q1p2npp/1p1pNp2/3Pn3/1PN3P1/PQ1BPPBP/2R2RK1 b - - 3 17": {
                "before": -45,  # From White's POV: White is -45cp (Black is ahead by 45cp)
                "after_played": -38,  # After Black plays Nxd2, White is -38cp (Black lost ~7cp advantage)
                "top_moves": [
                    {"uci": "g7c3", "cp": -45, "depth": 20},  # Best move (maintains -45cp evaluation)
                    {"uci": "e4d2", "cp": -38, "depth": 20},  # Nxd2 (played, loses 7cp: accurate KBE)
                    {"uci": "f6d7", "cp": -40, "depth": 20},
                ],
                "after_recapture": [
                    {"uci": "b3d2", "cp": 38, "depth": 20},  # After White recaptures Nxd2
                    {"uci": "b2d2", "cp": 42, "depth": 20},  # Qxd2 recapture
                    {"uci": "c1d2", "cp": 45, "depth": 20},
                ],
            },

            # Italian Game: Bxf7+ (accurate KBE, ~5cp sacrifice)
            "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 4 5": {
                "before": 18,  # White slightly better
                "after_played": 13,  # Bxf7+ loses ~5cp but ok
                "top_moves": [
                    {"uci": "d3d4", "cp": 25, "depth": 20},  # Best move
                    {"uci": "c4f7", "cp": 13, "depth": 20},  # Bxf7+ (played, KBE-like)
                    {"uci": "b1c3", "cp": 20, "depth": 20},
                    {"uci": "e1g1", "cp": 18, "depth": 20},
                ],
                "after_recapture": [
                    {"uci": "e8f7", "cp": -13, "depth": 20},  # Kxf7 recapture
                    {"uci": "d8e7", "cp": -18, "depth": 20},
                    {"uci": "g8e7", "cp": -20, "depth": 20},
                ],
            },

            # Test 2: inaccurate KBE - White Bxf6 (~15cp loss)
            # Scores from WHITE's perspective
            "r3kb1r/pp1b1ppp/1qn1pn2/2pp2B1/3P4/1QP1P3/PP1NBPPP/R3K1NR w KQkq - 4 8": {
                "before": 35,  # From White's POV: White is +35cp ahead
                "after_played": 20,  # After White plays Bxf6, White is +20cp (lost ~15cp)
                "top_moves": [
                    {"uci": "e1g1", "cp": 38, "depth": 20},  # Best move
                    {"uci": "g5f6", "cp": 20, "depth": 20},  # Bxf6 (played, inaccurate KBE)
                    {"uci": "d2f3", "cp": 32, "depth": 20},
                ],
                "after_recapture": [
                    {"uci": "d7f6", "cp": -20, "depth": 20},  # After Black recaptures Bxf6
                    {"uci": "g7f6", "cp": -25, "depth": 20},  # gxf6 recapture
                    {"uci": "b6f6", "cp": -28, "depth": 20},
                ],
            },

            # Test 3: bad KBE - Black Bxd4 (~35cp loss)
            # Scores from WHITE's perspective
            "1r3rk1/p4pb1/bq2p2p/3p2p1/3N4/1PP1P1P1/P2QPRBP/R5K1 b - - 2 22": {
                "before": -60,  # From White's POV: White is -60cp (Black is ahead)
                "after_played": -25,  # After Black plays Bxd4, White is -25cp (Black lost ~35cp advantage)
                "top_moves": [
                    {"uci": "b8b3", "cp": -65, "depth": 20},  # Best move (White is -65cp)
                    {"uci": "g7d4", "cp": -25, "depth": 20},  # Bxd4 (played, bad KBE)
                    {"uci": "b6d4", "cp": -30, "depth": 20},
                ],
                "after_recapture": [
                    {"uci": "e3d4", "cp": 25, "depth": 20},  # After White recaptures exd4
                    {"uci": "c3d4", "cp": 30, "depth": 20},  # cxd4 recapture
                    {"uci": "d2d4", "cp": 28, "depth": 20},
                ],
            },

            # Old test positions kept for compatibility with test_kbe_diagnostics_structure
            # QGD: Nxd5 (legacy test data)
            "r1bqkb1r/pp3ppp/2n1pn2/3p4/2PP4/2N1PN2/PP3PPP/R1BQKB1R w KQkq - 0 7": {
                "before": 32,
                "after_played": 25,
                "top_moves": [
                    {"uci": "c4d5", "cp": 35, "depth": 20},
                    {"uci": "c3d5", "cp": 25, "depth": 20},
                    {"uci": "c1e3", "cp": 30, "depth": 20},
                ],
                "after_recapture": [
                    {"uci": "c6d5", "cp": -25, "depth": 20},
                    {"uci": "e6d5", "cp": -28, "depth": 20},
                    {"uci": "f6e4", "cp": -30, "depth": 20},
                ],
            },

            # QGD variant 2 (legacy)
            "r1bqkb1r/pp2pppp/2n2n2/3p4/2PP4/2N1PN2/PP3PPP/R1BQKB1R w KQkq - 0 6": {
                "before": 28,
                "after_played": 13,
                "top_moves": [
                    {"uci": "c4d5", "cp": 30, "depth": 20},
                    {"uci": "c3d5", "cp": 13, "depth": 20},
                    {"uci": "c1e3", "cp": 25, "depth": 20},
                ],
                "after_recapture": [
                    {"uci": "c6d5", "cp": -13, "depth": 20},
                    {"uci": "e6d5", "cp": -18, "depth": 20},
                    {"uci": "f6e4", "cp": -20, "depth": 20},
                ],
            },

            # Bad KBE legacy position
            "r1bqk2r/ppp2ppp/2n1bn2/3p4/1bPP4/2N1PN2/PP2BPPP/R1BQK2R w KQkq - 4 7": {
                "before": 40,
                "after_played": 5,
                "top_moves": [
                    {"uci": "e1g1", "cp": 45, "depth": 20},
                    {"uci": "a2a3", "cp": 40, "depth": 20},
                    {"uci": "c1e3", "cp": 35, "depth": 20},
                ],
                "after_recapture": [
                    {"uci": "c6e5", "cp": -5, "depth": 20},
                    {"uci": "b7b6", "cp": -10, "depth": 20},
                    {"uci": "d5d4", "cp": -15, "depth": 20},
                ],
            },

            # Starting position - non-KBE move (pawn advance)
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1": {
                "before": 20,
                "after_played": 18,
                "top_moves": [
                    {"uci": "e2e4", "cp": 20, "depth": 20},
                    {"uci": "d2d4", "cp": 18, "depth": 20},
                    {"uci": "g1f3", "cp": 15, "depth": 20},
                ],
                "after_recapture": [],  # No recapture possible
            },

            # Exchange offer scenario: White plays Bg3 inviting Bxg3
            "r3r1k1/pp2nppp/1qnb2b1/3p4/3N3B/1NP5/PP2BPPP/R2QR1K1 w - - 1 16": {
                "before": 21,
                "after_played": 20,
                "top_moves": [
                    {"uci": "h4g3", "cp": 20, "depth": 20},
                    {"uci": "h4g5", "cp": 24, "depth": 20},
                    {"uci": "b3d4", "cp": 22, "depth": 20},
                ],
                "after_recapture": [],
            },
        }

    def analyse(
        self,
        board: chess.Board,
        limit: chess.engine.Limit,
        multipv: Optional[int] = None,
    ):
        """
        Mock engine analysis returning canned evaluations.

        Args:
            board: Chess board position
            limit: Analysis limit (depth/time)
            multipv: Number of principal variations (default: 1)

        Returns:
            Dict when multipv is None (no multipv specified)
            List[Dict] when multipv >= 1 (matches engine_io.py expectations)
        """
        # If multipv is specified (even multipv=1), delegate to analyse_multipv
        # This matches engine_io.py which always uses multipv parameter
        if multipv is not None:
            return self.analyse_multipv(board, limit, multipv)

        # multipv is None - return single dict for simple analyses (e.g., prophylaxis)
        fen_key = board.fen()

        # Find matching position (ignore move counters)
        eval_data = None
        stored_fen_match = None
        last_move_uci = None

        for stored_fen, data in self._evaluations.items():
            if self._fen_matches(fen_key, stored_fen):
                eval_data = data
                stored_fen_match = stored_fen
                break

        # If not found and we have move_stack, try parent position
        if not eval_data and board.move_stack:
            last_move = board.peek()
            last_move_uci = last_move.uci()
            board.pop()
            parent_fen = board.fen()
            board.push(last_move)

            for stored_fen, data in self._evaluations.items():
                if self._fen_matches(parent_fen, stored_fen):
                    eval_data = data
                    stored_fen_match = stored_fen
                    break

        if not eval_data:
            # Default fallback for unknown positions
            return {
                "score": chess.engine.PovScore(
                    chess.engine.Cp(0), board.turn
                ),
                "pv": [],
                "depth": limit.depth or 20,
            }

        # Determine which evaluation to return
        cp_score = eval_data["before"]

        # If we found the parent position and last move was played
        if board.move_stack and last_move_uci:
            # Check if this is the "after_played" scenario
            for move_data in eval_data["top_moves"]:
                if move_data["uci"] == last_move_uci:
                    # This is after the played move
                    cp_score = eval_data["after_played"]
                    break

        # Scores in _evaluations are from WHITE's POV
        # Return as-is without conversion - analysis.py uses .pov(board.turn)
        # which would convert them, but we're directly creating PovScore here
        # so we need to keep them in WHITE's POV
        return {
            "score": chess.engine.PovScore(
                chess.engine.Cp(cp_score), chess.WHITE
            ),
            "pv": [chess.Move.from_uci(eval_data["top_moves"][0]["uci"])],
            "depth": limit.depth or 20,
        }

    def analyse_multipv(
        self,
        board: chess.Board,
        limit: chess.engine.Limit,
        multipv: int = 4,
    ) -> List[Dict]:
        """
        Return multiple principal variations (for top-N move analysis).

        Used by detectors that check opponent's top-N responses.

        Key logic:
        - If no moves: return "top_moves" from current position
        - If last move was a capture: try to return "after_recapture" from parent position
        - Otherwise: return "top_moves" from current position
        """
        fen_key = board.fen()

        # First, try to find eval_data for current position
        eval_data = None
        for stored_fen, data in self._evaluations.items():
            if self._fen_matches(fen_key, stored_fen):
                eval_data = data
                break

        # If current position not found AND there's a move_stack,
        # try to find parent position and return recapture options
        if not eval_data and board.move_stack:
            last_move = board.peek()
            board.pop()
            parent_fen = board.fen()
            was_capture = board.is_capture(last_move)
            board.push(last_move)

            # Find parent position
            for stored_fen, data in self._evaluations.items():
                if self._fen_matches(parent_fen, stored_fen):
                    eval_data = data
                    # If last move was capture, use after_recapture list
                    # Scores in _evaluations are from WHITE's POV
                    if was_capture and data.get("after_recapture"):
                        results = []
                        for move_data in data["after_recapture"][:multipv]:
                            results.append({
                                "score": chess.engine.PovScore(
                                    chess.engine.Cp(move_data["cp"]), chess.WHITE
                                ),
                                "pv": [chess.Move.from_uci(move_data["uci"])],
                                "depth": move_data.get("depth", 20),
                            })
                        return results
                    break

        # If still no eval_data found, return default
        if not eval_data:
            default = {
                "score": chess.engine.PovScore(chess.engine.Cp(0), board.turn),
                "pv": [],
                "depth": limit.depth or 20,
            }
            return [default]

        # Return top_moves for current position
        # Scores in _evaluations are from WHITE's POV
        move_list = eval_data.get("top_moves", [])
        results = []
        for move_data in move_list[:multipv]:
            results.append({
                "score": chess.engine.PovScore(
                    chess.engine.Cp(move_data["cp"]), chess.WHITE
                ),
                "pv": [chess.Move.from_uci(move_data["uci"])],
                "depth": move_data.get("depth", 20),
            })

        return results if results else [{
            "score": chess.engine.PovScore(chess.engine.Cp(0), board.turn),
            "pv": [],
            "depth": limit.depth or 20,
        }]

    def play(
        self,
        board: chess.Board,
        limit: chess.engine.Limit,
    ):
        """
        Mock engine play - returns best move from top_moves.

        Returns a PlayResult-like object with move attribute.
        """
        # Get top moves via analyse_multipv
        lines = self.analyse_multipv(board, limit, multipv=1)
        best_move = None

        if lines and "pv" in lines[0] and lines[0]["pv"]:
            candidate_move = lines[0]["pv"][0]
            # Verify move is legal in current position
            if candidate_move in board.legal_moves:
                best_move = candidate_move

        # Fallback: pick any legal move
        if best_move is None:
            legal_moves = list(board.legal_moves)
            best_move = legal_moves[0] if legal_moves else None

        # Return object with move attribute
        class PlayResult:
            def __init__(self, move):
                self.move = move

        return PlayResult(best_move)

    def _fen_matches(self, fen1: str, fen2: str) -> bool:
        """Compare FENs ignoring move counters"""
        # Strip halfmove/fullmove clocks
        parts1 = fen1.split()[:4]
        parts2 = fen2.split()[:4]
        return parts1 == parts2

    def quit(self):
        """Stub for engine cleanup"""
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.quit()


def get_mock_engine() -> MockEngine:
    """Factory function for creating mock engine instances."""
    return MockEngine()
