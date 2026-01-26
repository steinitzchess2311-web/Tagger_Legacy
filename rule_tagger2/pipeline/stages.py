"""
Pipeline stages for staged rule tagging.
"""
from __future__ import annotations

from typing import List, Protocol

from ..engine import EngineClient
from ..features import build_feature_bundle
from ..gating import HardThresholdSelector, ModeSelector
from ..models import FinalResult, ModeDecision
from ..tagging import assemble_tags
from .context import PipelineContext


class Stage(Protocol):
    def run(self, ctx: PipelineContext) -> None:
        ...


class EngineStage:
    def __init__(self, *, depth: int, multipv: int, depth_low: int = 0) -> None:
        self._depth = depth
        self._multipv = multipv
        self._depth_low = depth_low

    def run(self, ctx: PipelineContext) -> None:
        ctx.engine_out = ctx.engine.analyze(
            ctx.fen,
            depth=self._depth,
            multipv=self._multipv,
            depth_low=self._depth_low,
        )


class FeatureStage:
    def run(self, ctx: PipelineContext) -> None:
        if ctx.engine_out is None:
            raise RuntimeError("EngineStage must run before FeatureStage")
        ctx.features = build_feature_bundle(
            ctx.fen,
            ctx.played_move_uci,
            ctx.engine_out,
            engine_client=ctx.engine,
            cp_threshold=ctx.cp_threshold,
            eval_depth=ctx.engine_depth,
            followup_depth=ctx.followup_depth,
            followup_steps=ctx.followup_steps,
        )


class ModeStage:
    def __init__(self, selector: ModeSelector | None = None) -> None:
        self._selector = selector or HardThresholdSelector()

    def run(self, ctx: PipelineContext) -> None:
        if ctx.features is None:
            raise RuntimeError("FeatureStage must run before ModeStage")
        ctx.mode = self._selector.decide(ctx.features)


class TaggingStage:
    def run(self, ctx: PipelineContext) -> None:
        if ctx.features is None or ctx.mode is None:
            raise RuntimeError("ModeStage must run before TaggingStage")
        bundle, legacy = assemble_tags(ctx, ctx.features, ctx.mode)
        ctx.tags = bundle
        ctx.metadata.setdefault("legacy_result", legacy)


class FinalizeStage:
    def run(self, ctx: PipelineContext) -> None:
        if ctx.features is None or ctx.mode is None or ctx.tags is None:
            raise RuntimeError("All stages must complete before FinalizeStage")
        ctx.final = FinalResult(
            features=ctx.features,
            mode=ctx.mode,
            tags=ctx.tags,
            raw_result=ctx.metadata.get("legacy_result"),
        )


def run_pipeline(ctx: PipelineContext, stages: List[Stage]) -> FinalResult:
    for stage in stages:
        stage.run(ctx)
    if ctx.final is None:
        raise RuntimeError("Pipeline did not produce a FinalResult")
    return ctx.final
