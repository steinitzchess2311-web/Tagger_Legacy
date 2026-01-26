import math
import random
import statistics
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

import chess
import chess.engine


@dataclass(frozen=True)
class PlanDropResult:
    psi: float
    pei: float
    plan_loss: float
    multipv: int
    depth: int
    stable: bool
    runtime_ms: float
    sampled: bool
    reasons: Tuple[str, ...]
    variance_before: float
    variance_after: float


PlanList = List[Tuple[str, int]]


@lru_cache(maxsize=512)
def _cached_plans(engine_path: str, fen: str, depth: int, multipv: int) -> PlanList:
    board = chess.Board(fen)
    try:
        with chess.engine.SimpleEngine.popen_uci(engine_path) as engine:
            info = engine.analyse(board, chess.engine.Limit(depth=depth), multipv=multipv)
    except Exception:
        return []

    plans: PlanList = []
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
    return plans


def detect_prophylaxis_plan_drop(
    engine_path: str,
    board_before: chess.Board,
    board_after: chess.Board,
    *,
    depth: int,
    multipv: int,
    sample_rate: float,
    variance_cap: float,
    runtime_cap_ms: float,
) -> Optional[PlanDropResult]:
    """Measure how much the played move disrupted the opponent's plans."""
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
        before_plans = _cached_plans(engine_path, baseline.fen(), depth, multipv)
    else:
        before_plans = []

    if not before_plans:
        return None

    start = time.perf_counter()
    after_plans = _cached_plans(engine_path, board_after.fen(), depth, multipv)
    if not after_plans:
        return None
    runtime_ms = (time.perf_counter() - start) * 1000.0

    mean_before = sum(score for _, score in before_plans) / len(before_plans)
    mean_after = sum(score for _, score in after_plans) / len(after_plans)
    pei_cp = mean_before - mean_after
    pei = pei_cp / 100.0  # convert to pawns

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
    variance_before = statistics.pvariance(values_before) if len(values_before) > 1 else 0.0
    variance_after = statistics.pvariance(values_after) if len(values_after) > 1 else 0.0
    stable = (
        variance_before <= variance_cap * 10000
        and variance_after <= variance_cap * 10000
        and runtime_ms <= runtime_cap_ms
    )
    reasons: List[str] = []
    if runtime_ms > runtime_cap_ms:
        reasons.append("runtime_cap")
    if variance_before > variance_cap * 10000 or variance_after > variance_cap * 10000:
        reasons.append("variance_cap")
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
