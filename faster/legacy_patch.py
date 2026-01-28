from __future__ import annotations

import contextlib
import math
import random
import time
from typing import Any, Dict, Iterator, List, Tuple

import chess

from engine_utils.prophylaxis import PlanDropResult
from rule_tagger2.core.engine_io import (
    contact_profile,
    estimate_phase_ratio,
    simulate_followup_metrics,
)
from rule_tagger2.legacy.move_utils import classify_move
from rule_tagger2.models import Candidate

from .cache import EngineCache
from .engine_session import EngineSession


class _ReuseEngineContext:
    def __init__(self, engine):
        self._engine = engine

    def __enter__(self):
        return self._engine

    def __exit__(self, exc_type, exc, tb):
        return False


def _analyse_candidates_fast(
    engine_path: str,
    board: chess.Board,
    depth: int,
    multipv: int,
    *,
    depth_low: int | None,
    session: EngineSession,
    cache: EngineCache,
) -> Tuple[List[Candidate], int, Dict[str, Any]]:
    fen = board.fen()
    depth_high = max(depth + 4, depth + 2)
    key = ("analyse_candidates", fen, depth, multipv, depth_low, depth_high)
    if key in cache.analyse_candidates:
        return cache.analyse_candidates[key]

    engine = session.engine
    if engine is None:
        raise RuntimeError("Engine session not initialized.")

    contact_ratio, total_moves, capture_count, checking_count = contact_profile(board)

    low_cp = None
    low_score = None
    if depth_low and depth_low < depth:
        low_info = engine.analyse(board, chess.engine.Limit(depth=depth_low), multipv=1)
        low_root = low_info[0] if isinstance(low_info, list) else low_info
        low_score = low_root["score"].pov(board.turn)
        low_cp = low_score.score(mate_score=10000)

    root = engine.analyse(board, chess.engine.Limit(depth=depth), multipv=max(1, multipv))
    root1 = root[0]
    root_score = root1["score"].pov(board.turn)
    eval_before_cp = root_score.score(mate_score=10000)

    high_cp = None
    high_score = None
    if depth_high > depth:
        high_info = engine.analyse(board, chess.engine.Limit(depth=depth_high), multipv=1)
        high_root = high_info[0] if isinstance(high_info, list) else high_info
        high_score = high_root["score"].pov(board.turn)
        high_cp = high_score.score(mate_score=10000)

    cands: List[Candidate] = []
    for line in root:
        if "pv" not in line or not line["pv"]:
            continue
        mv = line["pv"][0]
        sc = line["score"].pov(board.turn).score(mate_score=10000)
        cands.append(Candidate(move=mv, score_cp=sc, kind=classify_move(board, mv)))

    cands.sort(key=lambda c: c.score_cp, reverse=True)
    score_gap_cp = cands[0].score_cp - cands[1].score_cp if len(cands) > 1 else 0
    depth_low_cp = low_cp if low_cp is not None else eval_before_cp
    depth_jump_cp = eval_before_cp - depth_low_cp
    depth_high_cp = high_cp if high_cp is not None else eval_before_cp

    contact_count = capture_count + checking_count
    mate_threat = root_score.is_mate() or (high_score.is_mate() if high_score else False)
    phase_ratio = estimate_phase_ratio(board)

    analysis_meta: Dict[str, Any] = {
        "score_gap_cp": score_gap_cp,
        "depth_jump_cp": depth_jump_cp,
        "deepening_gain_cp": depth_high_cp - eval_before_cp,
        "contact_ratio": contact_ratio,
        "contact_moves": contact_count,
        "capture_moves": capture_count,
        "checking_moves": checking_count,
        "total_moves": total_moves,
        "phase_ratio": round(phase_ratio, 3),
        "mate_threat": mate_threat,
    }
    analysis_meta.setdefault("engine_meta", {})
    analysis_meta["engine_meta"].update(
        {
            "depth_used": depth,
            "multipv": multipv,
            "depth_low": depth_low,
            "depth_high": depth_high,
        }
    )
    result = (cands, eval_before_cp, analysis_meta)
    cache.analyse_candidates[key] = result
    return result


def _eval_specific_move_fast(
    engine_path: str,
    board: chess.Board,
    move: chess.Move,
    depth: int,
    *,
    session: EngineSession,
    cache: EngineCache,
) -> int:
    next_board = board.copy(stack=False)
    next_board.push(move)
    key = ("eval_specific_move", next_board.fen(), depth)
    if key in cache.eval_specific:
        return cache.eval_specific[key]
    engine = session.engine
    if engine is None:
        raise RuntimeError("Engine session not initialized.")
    info = engine.analyse(next_board, chess.engine.Limit(depth=depth), multipv=1)
    root = info[0] if isinstance(info, list) else info
    score = root["score"].pov(not next_board.turn).score(mate_score=10000)
    cache.eval_specific[key] = score
    return score


def _simulate_followup_metrics_fast(
    engine: chess.engine.SimpleEngine | None,
    board: chess.Board,
    actor: chess.Color,
    steps: int,
    *,
    depth: int = 6,
    session: EngineSession,
    cache: EngineCache,
):
    key = ("followups", board.fen(), actor, steps, depth)
    if key in cache.followups:
        return cache.followups[key]
    if session.engine is None:
        raise RuntimeError("Engine session not initialized.")
    result = simulate_followup_metrics(session.engine, board, actor, steps=steps, depth=depth)
    cache.followups[key] = result
    return result


def _estimate_opponent_threat_fast(
    engine_path: str,
    board: chess.Board,
    actor: chess.Color,
    *,
    config,
    session: EngineSession,
    cache: EngineCache,
) -> float:
    key = ("opp_threat", board.fen(), actor, config.threat_depth, config.safety_cap)
    if key in cache.threats:
        return cache.threats[key]
    if session.engine is None:
        raise RuntimeError("Engine session not initialized.")
    temp = board.copy(stack=False)
    if temp.is_game_over():
        return 0.0
    needs_null = temp.turn == actor
    null_pushed = False
    try:
        if needs_null and not temp.is_check():
            try:
                temp.push(chess.Move.null())
                null_pushed = True
            except ValueError:
                null_pushed = False
        depth = max(config.threat_depth, 8)
        info = session.engine.analyse(temp, chess.engine.Limit(depth=depth))
    except Exception:
        if null_pushed:
            temp.pop()
        return 0.0
    finally:
        if null_pushed and len(temp.move_stack) and temp.move_stack[-1] == chess.Move.null():
            temp.pop()

    score_obj = info.get("score")
    if score_obj is None:
        return 0.0
    try:
        pov_score = score_obj.pov(actor)
    except Exception:
        return 0.0

    if pov_score.is_mate():
        mate_in = pov_score.mate()
        if mate_in is None or mate_in > 0:
            return 0.0
        threat = 10.0 / (abs(mate_in) + 1)
    else:
        cp_value = pov_score.score(mate_score=10000) or 0
        threat = max(0.0, -cp_value / 100.0)

    result = round(min(threat, config.safety_cap), 3)
    cache.threats[key] = result
    return result


def _cached_plans_fast(
    *,
    fen: str,
    depth: int,
    multipv: int,
    session: EngineSession,
    cache: EngineCache,
) -> List[Tuple[str, int]]:
    key = ("plans", fen, depth, multipv)
    if key in cache.plans:
        return cache.plans[key]
    if session.engine is None:
        raise RuntimeError("Engine session not initialized.")
    board = chess.Board(fen)
    try:
        info = session.engine.analyse(board, chess.engine.Limit(depth=depth), multipv=multipv)
    except Exception:
        return []
    plans: List[Tuple[str, int]] = []
    color = board.turn
    for line in info:
        pv = line.get("pv")
        if not pv:
            continue
        move = pv[0]
        score_obj = line.get("score")
        if score_obj is None:
            continue
        try:
            score_cp = score_obj.pov(color).score(mate_score=10000)
        except Exception:
            continue
        if score_cp is None:
            continue
        plans.append((move.uci(), score_cp))
    cache.plans[key] = plans
    return plans


def _detect_prophylaxis_plan_drop_fast(
    engine_path: str,
    board_before: chess.Board,
    board_after: chess.Board,
    *,
    depth: int,
    multipv: int,
    sample_rate: float,
    variance_cap: float,
    runtime_cap_ms: float,
    session: EngineSession,
    cache: EngineCache,
):
    if depth <= 0 or multipv <= 1:
        return None

    if board_before.is_check():
        return None

    if sample_rate < 1.0 and random.random() > sample_rate:
        return PlanDropResult(
            psi=0.0,
            pei=0.0,
            plan_loss=0.0,
            multipv=multipv,
            depth=depth,
            stable=False,
            runtime_ms=0.0,
            sampled=False,
            reasons=("sample_skipped",),
            variance_before=0.0,
            variance_after=0.0,
        )

    baseline = board_before.copy(stack=False)
    try:
        baseline.push(chess.Move.null())
    except ValueError:
        return None
    if baseline.turn == board_after.turn:
        before_plans = _cached_plans_fast(
            fen=baseline.fen(), depth=depth, multipv=multipv, session=session, cache=cache
        )
    else:
        before_plans = []
    if not before_plans:
        return None

    start = time.perf_counter()
    after_plans = _cached_plans_fast(
        fen=board_after.fen(), depth=depth, multipv=multipv, session=session, cache=cache
    )
    if not after_plans:
        return None
    runtime_ms = (time.perf_counter() - start) * 1000.0

    mean_before = sum(score for _, score in before_plans) / len(before_plans)
    mean_after = sum(score for _, score in after_plans) / len(after_plans)
    pei_cp = mean_before - mean_after
    pei = pei_cp / 100.0

    after_ranks: Dict[str, int] = {move: idx for idx, (move, _) in enumerate(after_plans)}
    plan_loss_acc = 0.0
    for idx, (move, _) in enumerate(before_plans):
        rank_after = after_ranks.get(move)
        if rank_after is None:
            plan_loss_acc += multipv
        else:
            plan_loss_acc += max(0, rank_after - idx)
    plan_loss = plan_loss_acc / max(1, multipv)

    values_before = [score for _, score in before_plans]
    values_after = [score for _, score in after_plans]
    variance_before = 0.0
    variance_after = 0.0
    if len(values_before) > 1:
        mean_b = sum(values_before) / len(values_before)
        variance_before = sum((v - mean_b) ** 2 for v in values_before) / len(values_before)
    if len(values_after) > 1:
        mean_a = sum(values_after) / len(values_after)
        variance_after = sum((v - mean_a) ** 2 for v in values_after) / len(values_after)

    stable = (
        variance_before <= variance_cap * 10000
        and variance_after <= variance_cap * 10000
        and runtime_ms <= runtime_cap_ms
    )
    reasons: List[str] = []
    sampled = True

    combined = 0.7 * pei + 0.3 * plan_loss
    psi = 1.0 / (1.0 + math.exp(-combined / 0.4))
    return PlanDropResult(
        psi=round(psi, 3),
        pei=round(pei, 3),
        plan_loss=round(plan_loss, 3),
        multipv=multipv,
        depth=depth,
        stable=stable,
        runtime_ms=round(runtime_ms, 2),
        sampled=sampled,
        reasons=tuple(reasons),
        variance_before=round(variance_before / 10000, 3),
        variance_after=round(variance_after / 10000, 3),
    )


@contextlib.contextmanager
def patch_legacy_for_fast(session: EngineSession, cache: EngineCache) -> Iterator[None]:
    import rule_tagger2.legacy.core as legacy_core

    original = {
        "analyse_candidates": legacy_core.analyse_candidates,
        "eval_specific_move": legacy_core.eval_specific_move,
        "simulate_followup_metrics": legacy_core.simulate_followup_metrics,
        "estimate_opponent_threat": legacy_core.estimate_opponent_threat,
        "detect_prophylaxis_plan_drop": legacy_core.detect_prophylaxis_plan_drop,
        "popen_uci": legacy_core.chess.engine.SimpleEngine.popen_uci,
    }

    legacy_core.analyse_candidates = lambda engine_path, board, depth=14, multipv=6, depth_low=6: _analyse_candidates_fast(  # type: ignore
        engine_path,
        board,
        depth,
        multipv,
        depth_low=depth_low,
        session=session,
        cache=cache,
    )
    legacy_core.eval_specific_move = lambda engine_path, board, move, depth=14: _eval_specific_move_fast(  # type: ignore
        engine_path,
        board,
        move,
        depth,
        session=session,
        cache=cache,
    )
    legacy_core.simulate_followup_metrics = lambda engine, board, actor, steps, depth=6: _simulate_followup_metrics_fast(  # type: ignore
        engine,
        board,
        actor,
        steps,
        depth=depth,
        session=session,
        cache=cache,
    )
    legacy_core.estimate_opponent_threat = lambda engine_path, board, actor, config: _estimate_opponent_threat_fast(  # type: ignore
        engine_path,
        board,
        actor,
        config=config,
        session=session,
        cache=cache,
    )
    legacy_core.detect_prophylaxis_plan_drop = lambda engine_path, board_before, board_after, depth, multipv, sample_rate, variance_cap, runtime_cap_ms: _detect_prophylaxis_plan_drop_fast(  # type: ignore
        engine_path,
        board_before,
        board_after,
        depth=depth,
        multipv=multipv,
        sample_rate=sample_rate,
        variance_cap=variance_cap,
        runtime_cap_ms=runtime_cap_ms,
        session=session,
        cache=cache,
    )
    legacy_core.chess.engine.SimpleEngine.popen_uci = lambda engine_path: _ReuseEngineContext(session.engine)  # type: ignore

    try:
        yield
    finally:
        legacy_core.analyse_candidates = original["analyse_candidates"]
        legacy_core.eval_specific_move = original["eval_specific_move"]
        legacy_core.simulate_followup_metrics = original["simulate_followup_metrics"]
        legacy_core.estimate_opponent_threat = original["estimate_opponent_threat"]
        legacy_core.detect_prophylaxis_plan_drop = original["detect_prophylaxis_plan_drop"]
        legacy_core.chess.engine.SimpleEngine.popen_uci = original["popen_uci"]
