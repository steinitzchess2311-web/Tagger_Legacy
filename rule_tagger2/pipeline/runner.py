"""
Convenience runner for the staged pipeline.
"""
from __future__ import annotations

from typing import Iterable, List

from ..engine import EngineClient
from ..models import FinalResult
from .context import PipelineContext
from .stages import EngineStage, FeatureStage, ModeStage, TaggingStage, FinalizeStage, Stage, run_pipeline


class TaggingPipeline:
    def __init__(
        self,
        engine: EngineClient,
        *,
        depth: int = 14,
        multipv: int = 6,
        cp_threshold: int = 100,
        depth_low: int = 6,
        stages: Iterable[Stage] | None = None,
    ) -> None:
        self._engine = engine
        self._depth = depth
        self._multipv = multipv
        self._cp_threshold = cp_threshold
        self._depth_low = depth_low
        if stages is None:
            self._stages = [
                EngineStage(depth=depth, multipv=multipv, depth_low=depth_low),
                FeatureStage(),
                ModeStage(),
                TaggingStage(),
                FinalizeStage(),
            ]
        else:
            self._stages = list(stages)

    def evaluate(self, fen: str, played_move_uci: str) -> FinalResult:
        ctx = PipelineContext(
            fen=fen,
            played_move_uci=played_move_uci,
            engine=self._engine,
            engine_depth=self._depth,
            engine_multipv=self._multipv,
            cp_threshold=self._cp_threshold,
        )
        return run_pipeline(ctx, self._stages)


def run_pipeline_wrapper(ctx: PipelineContext) -> FinalResult:
    default_stages: List[Stage] = [
        EngineStage(depth=ctx.engine_depth, multipv=ctx.engine_multipv),
        FeatureStage(),
        ModeStage(),
        TaggingStage(),
        FinalizeStage(),
    ]
    return run_pipeline(ctx, default_stages)


__all__ = ["TaggingPipeline", "run_pipeline", "run_pipeline_wrapper"]
