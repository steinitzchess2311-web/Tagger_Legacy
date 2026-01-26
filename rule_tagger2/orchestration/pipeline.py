"""
Tag detection pipeline orchestrator.

This module coordinates the execution of all tag detectors in priority order.
Initially, it's a passthrough to legacy code for zero-behavior-change migration.

IMPORTANT: This is a skeleton for gradual migration.
- Phase 1 (P1): Passthrough to legacy (this file)
- Phase 2 (P2-P3): Gradually call new detectors, fallback to legacy
- Phase 4+: Fully replace legacy

Current Status: P2 Day 3 - TensionDetector & ProphylaxisDetector integrated

Environment Variables:
- USE_NEW_TENSION: Set to "1" to enable new TensionDetector (default: "0", uses legacy)
- USE_NEW_COD: Set to "1" to enable new ControlOverDynamicsV2Detector (default: "0", uses ProphylaxisDetector)
- USE_SPLIT_TENSION_V2: Set to "1" to enable stricter tension boundary v2 (default: "0", uses legacy gates)
"""
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import chess
import os

from .context import AnalysisContext
from ..detectors.base import TagDetector
from ..legacy.thresholds import THRESHOLDS

# Avoid circular import: import detectors only when type checking
if TYPE_CHECKING:
    from ..detectors.tension import TensionDetector
    from ..detectors.prophylaxis import ProphylaxisDetector


class TagDetectionPipeline:
    """
    Orchestrates tag detection across multiple detectors.

    The pipeline:
    1. Builds AnalysisContext from position data
    2. Runs applicable detectors in priority order
    3. Applies gating rules (tactical weight, cooldown, etc.)
    4. Assembles final result

    Migration Strategy:
    - P1: Returns legacy result (passthrough)
    - P2: Calls 3 new detectors (tension, prophylaxis, control) + legacy for rest
    - P3: Calls all new detectors, legacy only for gaps
    - P4+: No legacy dependency
    """

    def __init__(self, use_legacy: bool = True):
        """
        Initialize pipeline.

        Args:
            use_legacy: If True, use legacy tag_position (default for P1)
        """
        self.use_legacy = use_legacy
        self.detectors: List[TagDetector] = []
        self._legacy_available = self._check_legacy_available()

    def _check_legacy_available(self) -> bool:
        """Check if legacy code is available."""
        try:
            from ..legacy.core import tag_position  # noqa: F401
            return True
        except ImportError:
            return False

    def register_detector(self, detector: TagDetector):
        """
        Register a detector to the pipeline.

        Args:
            detector: TagDetector instance
        """
        self.detectors.append(detector)
        # Sort by priority after registration
        self.detectors.sort(key=lambda d: d.get_priority())

    def run_pipeline(
        self,
        engine_path: str,
        fen: str,
        played_move_uci: str,
        depth: int = 14,
        multipv: int = 6,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Run the full tag detection pipeline.

        P1 Implementation: Passthrough to legacy tag_position.
        Future: Build AnalysisContext → Run detectors → Apply gating → Build result

        Args:
            engine_path: Path to chess engine
            fen: FEN string
            played_move_uci: Move in UCI format
            depth: Engine analysis depth
            multipv: Multi-PV count
            **kwargs: Additional arguments

        Returns:
            Dictionary with tags, metadata, evidence, etc.
        """
        # P1: Passthrough to legacy
        if self.use_legacy and self._legacy_available:
            return self._run_legacy(
                engine_path=engine_path,
                fen=fen,
                played_move_uci=played_move_uci,
                depth=depth,
                multipv=multipv,
                **kwargs
            )

        # Future P2+: New detector path
        return self._run_new_detectors(
            engine_path=engine_path,
            fen=fen,
            played_move_uci=played_move_uci,
            depth=depth,
            multipv=multipv,
            **kwargs
        )

    def _run_legacy(
        self,
        engine_path: str,
        fen: str,
        played_move_uci: str,
        depth: int,
        multipv: int,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Run legacy tag_position and convert to standard format.

        Args:
            engine_path: Path to engine
            fen: FEN string
            played_move_uci: Move UCI
            depth: Analysis depth
            multipv: Multi-PV
            **kwargs: Additional args

        Returns:
            Result dictionary
        """
        from ..legacy.core import tag_position

        # Call legacy
        result = tag_position(
            engine_path=engine_path,
            fen=fen,
            played_move_uci=played_move_uci,
            depth=depth,
            multipv=multipv,
            **kwargs
        )

        # Mark result as legacy pipeline
        if hasattr(result, 'analysis_context') and isinstance(result.analysis_context, dict):
            engine_meta = result.analysis_context.setdefault("engine_meta", {})
            engine_meta["__new_pipeline__"] = False  # Legacy-only mode
            engine_meta["__orchestrator__"] = "rule_tagger2.legacy"

        # Convert TagResult to dict (if not already)
        if hasattr(result, 'to_dict'):
            return result.to_dict()
        elif hasattr(result, '__dict__'):
            return vars(result)
        else:
            return result

    def _run_new_detectors(
        self,
        engine_path: str,
        fen: str,
        played_move_uci: str,
        depth: int,
        multipv: int,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Run new detector-based pipeline (P2 Day 3 implementation).

        P2 Strategy: Run TensionDetector & ProphylaxisDetector, then call legacy for remaining tags.
        This allows gradual migration while maintaining backward compatibility.

        Args:
            engine_path: Path to engine
            fen: FEN string
            played_move_uci: Move UCI
            depth: Analysis depth
            multipv: Multi-PV
            **kwargs: Additional args

        Returns:
            Result dictionary with merged tags from new + legacy detectors
        """
        from ..legacy.core import tag_position

        # Step 1: Call legacy to get full context and baseline tags
        legacy_result = tag_position(
            engine_path=engine_path,
            fen=fen,
            played_move_uci=played_move_uci,
            depth=depth,
            multipv=multipv,
            **kwargs
        )

        # Step 2: Build AnalysisContext from legacy result for new detectors
        # (For now, we'll need to extract relevant data from legacy result)
        board = chess.Board(fen)
        played_move = chess.Move.from_uci(played_move_uci)

        # Create AnalysisContext with data from legacy result
        ctx = self._build_context_from_legacy(legacy_result, board, played_move, engine_path)

        # Step 3: Run TensionDetector (conditionally based on USE_NEW_TENSION)
        # Default: USE_NEW_TENSION=0 (use legacy tension tags)
        # Set USE_NEW_TENSION=1 to enable new TensionDetector
        use_new_tension = bool(int(os.getenv("USE_NEW_TENSION", "0")))

        if use_new_tension:
            from ..detectors.tension import TensionDetector
            tension_detector = TensionDetector()
            new_tension_tags = tension_detector.detect(ctx)

            # Update TagResult with new detection results
            legacy_result.tension_creation = "tension_creation" in new_tension_tags
            legacy_result.neutral_tension_creation = "neutral_tension_creation" in new_tension_tags

            # Store Tension v2 diagnostics in analysis_context
            if hasattr(legacy_result, 'analysis_context'):
                tension_metadata = tension_detector.get_metadata()
                legacy_result.analysis_context["tension_v2_diagnostics"] = {
                    "tags_found": tension_metadata.tags_found,
                    "diagnostic_info": tension_metadata.diagnostic_info,
                    "execution_time_ms": tension_metadata.execution_time_ms,
                    "version": "v2" if tension_detector._use_v2_boundary else "legacy",
                    "boundary_thresholds": {
                        "min_mobility_evidence": tension_detector._min_mobility_evidence,
                        "min_contact_evidence": tension_detector._min_contact_evidence,
                    }
                }
                # Copy tension_support to top-level for backward compatibility
                tension_support = tension_metadata.diagnostic_info.get("tension_support", {})
                if tension_support:
                    if "engine_meta" not in legacy_result.analysis_context:
                        legacy_result.analysis_context["engine_meta"] = {}
                    legacy_result.analysis_context["engine_meta"]["tension_support"] = tension_support
        # else: Keep legacy tension tags unchanged

        # Step 3b: Run CoD Detector (conditionally based on USE_NEW_COD)
        # Default: USE_NEW_COD=0 (use ProphylaxisDetector)
        # Set USE_NEW_COD=1 to enable new ControlOverDynamicsV2Detector
        use_new_cod = bool(int(os.getenv("USE_NEW_COD", "0")))

        if use_new_cod:
            # Use new ControlOverDynamicsV2Detector
            from ..cod_v2.detector import ControlOverDynamicsV2Detector
            from ..cod_v2.cod_types import CoDContext

            # Build CoDContext from AnalysisContext
            cod_ctx = self._build_cod_context(ctx, legacy_result)

            cod_detector = ControlOverDynamicsV2Detector()
            cod_result = cod_detector.detect(cod_ctx)

            # Convert CoD result to tags
            cod_tags = []
            if cod_result.detected:
                cod_tags.append("control_over_dynamics")
                if cod_result.subtype.value != "none":
                    cod_tags.append(f"control_over_dynamics:{cod_result.subtype.value}")

            # Update TagResult
            legacy_result.control_over_dynamics = cod_result.detected
            cod_subtype = cod_result.subtype.value if cod_result.detected else None

            # Clear all CoD subtype flags first (prevent legacy bleed-through)
            legacy_result.cod_simplify = False
            legacy_result.cod_plan_kill = False
            legacy_result.cod_freeze_bind = False
            legacy_result.cod_blockade_passed = False
            legacy_result.cod_file_seal = False
            legacy_result.cod_king_safety_shell = False
            legacy_result.cod_space_clamp = False
            legacy_result.cod_regroup_consolidate = False
            legacy_result.cod_slowdown = False

            # Set control_over_dynamics_subtype and corresponding flag
            if cod_result.detected and cod_subtype and cod_subtype != "none":
                legacy_result.control_over_dynamics_subtype = cod_subtype

                # Map CoD v2 subtypes to legacy boolean flags
                # CoD v2 uses: prophylaxis, piece_control, pawn_control, simplification
                # Legacy uses: 9 specific cod_* flags
                # Create a mapping for CoD v2 → legacy compatibility
                cod_v2_to_legacy_map = {
                    "simplification": "cod_simplify",
                    "prophylaxis": "cod_plan_kill",  # Map generic prophylaxis to plan_kill
                    "piece_control": "cod_freeze_bind",  # Map piece control to freeze/bind
                    "pawn_control": "cod_space_clamp",  # Map pawn control to space clamp
                }

                # Set the corresponding legacy flag
                legacy_flag = cod_v2_to_legacy_map.get(cod_subtype)
                if legacy_flag:
                    setattr(legacy_result, legacy_flag, True)
            else:
                legacy_result.control_over_dynamics_subtype = None

            # Store CoD v2 diagnostics in analysis_context
            if hasattr(legacy_result, 'analysis_context'):
                legacy_result.analysis_context["cod_v2_result"] = {
                    "detected": cod_result.detected,
                    "subtype": cod_result.subtype.value,
                    "gates_passed": cod_result.gates_passed,
                    "gates_failed": cod_result.gates_failed,
                    "diagnostic": cod_result.diagnostic,
                }
                if cod_subtype:
                    legacy_result.analysis_context["cod_subtype"] = cod_subtype
        else:
            # Use legacy ProphylaxisDetector
            from ..detectors.prophylaxis import ProphylaxisDetector
            prophylaxis_detector = ProphylaxisDetector()
            prophylaxis_tags = prophylaxis_detector.detect(ctx)

            # Step 4: Update TagResult with prophylaxis detection results

            # Update prophylaxis/control tags
            legacy_result.control_over_dynamics = "control_over_dynamics" in prophylaxis_tags

            # Extract COD subtype if present
            cod_subtype = None
            for tag in prophylaxis_tags:
                if tag.startswith("control_over_dynamics:"):
                    cod_subtype = tag.split(":", 1)[1]
                    break

            if cod_subtype:
                # Store subtype in analysis_context for telemetry
                if hasattr(legacy_result, 'analysis_context'):
                    legacy_result.analysis_context["cod_subtype"] = cod_subtype

            # Store Prophylaxis diagnostics in analysis_context
            if hasattr(legacy_result, 'analysis_context'):
                prophylaxis_metadata = prophylaxis_detector.get_metadata()
                legacy_result.analysis_context["prophylaxis_diagnostics"] = {
                    "tags_found": prophylaxis_metadata.tags_found,
                    "diagnostic_info": prophylaxis_metadata.diagnostic_info,
                    "execution_time_ms": prophylaxis_metadata.execution_time_ms,
                }
                # Store cod_support diagnostic info in engine_meta
                if prophylaxis_metadata.diagnostic_info:
                    if "engine_meta" not in legacy_result.analysis_context:
                        legacy_result.analysis_context["engine_meta"] = {}
                    legacy_result.analysis_context["engine_meta"]["cod_support"] = {
                        "suppressed_by": prophylaxis_metadata.diagnostic_info.get("suppressed", []),
                        "cooldown_hit": prophylaxis_metadata.diagnostic_info.get("cooldown_remaining", 0) > 0,
                        "all_detected": prophylaxis_metadata.diagnostic_info.get("all_detected", []),
                        "gate_log": prophylaxis_metadata.diagnostic_info.get("gate_log", {}),
                    }

            # Step 3c: Run FailedProphylacticDetector (after Prophylaxis sets the flag)
            # First, update ctx.metadata with prophylactic_move flag from legacy result
            ctx.metadata['prophylactic_move'] = (
                getattr(legacy_result, 'prophylactic_move', False)
                or ctx.metadata.get('prophylaxis_force_failure', False)
            )

            if ctx.metadata['prophylactic_move']:
                from ..detectors.failed_prophylactic import FailedProphylacticDetector
                failed_prophy_detector = FailedProphylacticDetector()
                failed_prophy_tags = failed_prophy_detector.detect(ctx)

                # Update TagResult with failed prophylactic detection
                legacy_result.failed_prophylactic = "failed_prophylactic" in failed_prophy_tags

                # Store diagnostics in analysis_context (for reporting/scripts)
                if hasattr(legacy_result, 'analysis_context'):
                    if "prophylaxis_diagnostics" not in legacy_result.analysis_context:
                        legacy_result.analysis_context["prophylaxis_diagnostics"] = {}

                    # Copy failure_check from ctx.metadata to analysis_context
                    # This mirrors the payload to analysis_meta as required by row 46
                    if "prophylaxis_diagnostics" in ctx.metadata and "failure_check" in ctx.metadata["prophylaxis_diagnostics"]:
                        failure_check_data = ctx.metadata["prophylaxis_diagnostics"]["failure_check"]
                        legacy_result.analysis_context["prophylaxis_diagnostics"]["failure_check"] = failure_check_data

                        # Also ensure ctx.analysis_meta exists and mirror there
                        if not hasattr(ctx, 'analysis_meta'):
                            ctx.analysis_meta = {}
                        if "prophylaxis_diagnostics" not in ctx.analysis_meta:
                            ctx.analysis_meta["prophylaxis_diagnostics"] = {}
                        ctx.analysis_meta["prophylaxis_diagnostics"]["failure_check"] = failure_check_data

        # Step 4: Run KnightBishopExchange detector (always active)
        from ..detectors.knight_bishop_exchange import KnightBishopExchangeDetector
        kbe_detector = KnightBishopExchangeDetector()

        # V2-kbe: ALWAYS write gating status (even when detector not applicable or no tags fire)
        # Initialize to False/None as default
        kbe_tags = []
        if kbe_detector.is_applicable(ctx):
            kbe_tags = kbe_detector.detect(ctx)

        # Update TagResult with KBE detection results
        legacy_result.accurate_knight_bishop_exchange = "accurate_knight_bishop_exchange" in kbe_tags
        legacy_result.inaccurate_knight_bishop_exchange = "inaccurate_knight_bishop_exchange" in kbe_tags
        legacy_result.bad_knight_bishop_exchange = "bad_knight_bishop_exchange" in kbe_tags

        # Mirror KBE tags into gating/tag_flags so downstream consumers see the new labels
        if hasattr(legacy_result, "analysis_context"):
            analysis_ctx = legacy_result.analysis_context
            tag_flags = analysis_ctx.setdefault("tag_flags", {})
            for tag in (
                "accurate_knight_bishop_exchange",
                "inaccurate_knight_bishop_exchange",
                "bad_knight_bishop_exchange",
            ):
                tag_flags[tag] = getattr(legacy_result, tag, False)

            engine_meta = analysis_ctx.setdefault("engine_meta", {})
            gating_block = engine_meta.setdefault("gating", {})
            primary_tags = gating_block.setdefault("tags_primary", [])
            for tag in kbe_tags:
                if tag not in primary_tags:
                    primary_tags.append(tag)

        # V2-kbe: Write KBE results to engine_meta["gating"] for pipeline/telemetry/dashboards
        # ALWAYS write gating status (True/False), regardless of is_applicable or tag detection
        if hasattr(legacy_result, 'analysis_context'):
            if "engine_meta" not in legacy_result.analysis_context:
                legacy_result.analysis_context["engine_meta"] = {}
            if "gating" not in legacy_result.analysis_context["engine_meta"]:
                legacy_result.analysis_context["engine_meta"]["gating"] = {}

            # Store KBE detection status (default False) and subtype (default None)
            legacy_result.analysis_context["engine_meta"]["gating"]["kbe_detected"] = len(kbe_tags) > 0
            legacy_result.analysis_context["engine_meta"]["gating"]["kbe_subtype"] = kbe_tags[0] if kbe_tags else None

        # Store KBE diagnostics in analysis_context (for reporting/scripts) - ONLY when tags fire
        if hasattr(legacy_result, 'analysis_context') and kbe_tags:
                kbe_metadata = kbe_detector.get_metadata()
                if "knight_bishop_exchange" not in legacy_result.analysis_context:
                    legacy_result.analysis_context["knight_bishop_exchange"] = {}

                # Copy from ctx.metadata (where detector wrote it) to analysis_context
                # This mirrors the payload to analysis_meta as required by row 42
                if "knight_bishop_exchange" in ctx.metadata:
                    kbe_diagnostics = ctx.metadata["knight_bishop_exchange"]
                    legacy_result.analysis_context["knight_bishop_exchange"].update(kbe_diagnostics)

                    # Also ensure ctx.analysis_meta exists and mirror there
                    if not hasattr(ctx, 'analysis_meta'):
                        ctx.analysis_meta = {}
                    if "knight_bishop_exchange" not in ctx.analysis_meta:
                        ctx.analysis_meta["knight_bishop_exchange"] = {}
                    ctx.analysis_meta["knight_bishop_exchange"].update(kbe_diagnostics)

                    # V2-kbe: Copy KBE diagnostics to kbe_support for UI/report layer
                    if "kbe_support" not in legacy_result.analysis_context:
                        legacy_result.analysis_context["kbe_support"] = {}
                    legacy_result.analysis_context["kbe_support"].update(kbe_diagnostics)

        # Demote low-impact constructive maneuvers triggered by pure exchange offers
        kbe_meta = ctx.metadata.get("knight_bishop_exchange", {})
        if (
            kbe_meta
            and kbe_meta.get("exchange_mode") == "offer"
            and getattr(legacy_result, "constructive_maneuver", False)
        ):
            precision = getattr(legacy_result, "maneuver_precision_score", 0.0)
            mobility_gain = (
                legacy_result.metrics_played.get("mobility", 0.0)
                - legacy_result.metrics_before.get("mobility", 0.0)
            )
            precision_guard = THRESHOLDS.get("maneuver_precision_guard_exchange", 0.25) or 0.25
            mobility_guard = THRESHOLDS.get("maneuver_low_impact_guard", 0.2) or 0.2
            if precision < precision_guard and mobility_gain <= mobility_guard:
                legacy_result.constructive_maneuver = False
                legacy_result.neutral_maneuver = True
                legacy_result.notes.setdefault(
                    "maneuver_adjust",
                    "downgraded constructive maneuver (low-impact exchange offer)",
                )
                analysis_ctx = getattr(legacy_result, "analysis_context", {})
                tag_flags = analysis_ctx.get("tag_flags")
                if tag_flags:
                    tag_flags["constructive_maneuver"] = False
                    tag_flags["neutral_maneuver"] = True
                gating = analysis_ctx.get("gating", {})
                tags_primary = gating.get("tags_primary")
                if isinstance(tags_primary, list):
                    gating["tags_primary"] = [tag for tag in tags_primary if tag != "constructive_maneuver"]
                    if "neutral_maneuver" not in gating["tags_primary"]:
                        gating["tags_primary"].append("neutral_maneuver")
                engine_meta = analysis_ctx.get("engine_meta", {})
                gating_meta = engine_meta.get("gating", {})
                meta_tags = gating_meta.get("tags_primary")
                if isinstance(meta_tags, list):
                    gating_meta["tags_primary"] = [tag for tag in meta_tags if tag != "constructive_maneuver"]
                    if "neutral_maneuver" not in gating_meta["tags_primary"]:
                        gating_meta["tags_primary"].append("neutral_maneuver")

        # Add metadata to indicate hybrid pipeline
        if hasattr(legacy_result, 'analysis_context'):
            engine_meta = legacy_result.analysis_context.setdefault("engine_meta", {})
            engine_meta["__pipeline_mode__"] = "hybrid_p2_day3"
            engine_meta["__new_pipeline__"] = not self.use_legacy  # True for new detectors, False for legacy-only
            new_detectors = []
            if use_new_tension:
                new_detectors.append("TensionDetector")
                engine_meta["__tension_detector_v2__"] = True
            if use_new_cod:
                new_detectors.append("ControlOverDynamicsV2")
                engine_meta["__cod_detector_v2__"] = True
            else:
                new_detectors.append("ProphylaxisDetector")
                engine_meta["__prophylaxis_detector_v2__"] = True
            new_detectors.append("KnightBishopExchangeDetector")
            engine_meta["__kbe_detector_v2__"] = True
            engine_meta["__new_detectors__"] = new_detectors

        # Return TagResult object directly (don't convert to dict)
        # This maintains compatibility with legacy interface
        return legacy_result

    def _build_context_from_legacy(
        self, legacy_result: Any, board: chess.Board, played_move: chess.Move, engine_path: str = ""
    ) -> AnalysisContext:
        """
        Build AnalysisContext from legacy TagResult.

        Args:
            legacy_result: TagResult from legacy tag_position
            board: Chess board
            played_move: Played move
            engine_path: Path to chess engine

        Returns:
            AnalysisContext populated with legacy data
        """
        # Extract analysis_context dict from legacy result
        analysis_ctx = getattr(legacy_result, 'analysis_context', {})

        # Build context for all detectors (TensionDetector, ProphylaxisDetector, KBE, etc.)
        ctx = AnalysisContext(board=board, played_move=played_move, actor=board.turn, engine_path=engine_path)

        # Populate evaluation fields from legacy result
        ctx.eval_before = getattr(legacy_result, 'eval_before', 0.0)
        ctx.eval_played = getattr(legacy_result, 'eval_played', 0.0)
        ctx.eval_best = getattr(legacy_result, 'eval_best', 0.0)
        ctx.eval_before_cp = int(ctx.eval_before * 100)
        ctx.eval_played_cp = int(ctx.eval_played * 100)
        ctx.eval_best_cp = int(ctx.eval_best * 100)

        # Populate from legacy analysis_context
        if isinstance(analysis_ctx, dict):
            # === Unpack engine_meta and merge all key fields ===
            engine_meta = analysis_ctx.get('engine_meta', {})
            if isinstance(engine_meta, dict):
                # Merge engine_meta fields into top-level metadata
                ctx.metadata['score_gap_cp'] = engine_meta.get('score_gap_cp', 0)
                ctx.metadata['depth_jump_cp'] = engine_meta.get('depth_jump_cp', 0)
                ctx.metadata['deepening_gain_cp'] = engine_meta.get('deepening_gain_cp', 0)
                ctx.metadata['contact_ratio'] = engine_meta.get('contact_ratio', 0.0)
                ctx.metadata['contact_moves'] = engine_meta.get('contact_moves', 0)
                ctx.metadata['capture_moves'] = engine_meta.get('capture_moves', 0)
                ctx.metadata['checking_moves'] = engine_meta.get('checking_moves', 0)
                ctx.metadata['total_moves'] = engine_meta.get('total_moves', 0)
                ctx.metadata['mate_threat'] = engine_meta.get('mate_threat', False)
                ctx.metadata['depth_used'] = engine_meta.get('depth_used', 14)
                ctx.metadata['multipv'] = engine_meta.get('multipv', 6)
                ctx.metadata['depth_low'] = engine_meta.get('depth_low', 6)
                ctx.metadata['depth_high'] = engine_meta.get('depth_high', 18)

                # Merge key detection support fields
                ctx.metadata['tension_support'] = engine_meta.get('tension_support', {})
                ctx.metadata['cod_support'] = engine_meta.get('cod_support', {})
                ctx.metadata['prophylaxis'] = engine_meta.get('prophylaxis', {})
                ctx.metadata['prophylaxis_plan'] = engine_meta.get('prophylaxis_plan', {})
                ctx.metadata['control_dynamics'] = engine_meta.get('control_dynamics', {})
                ctx.metadata['structural_details'] = engine_meta.get('structural_details', {})
                ctx.metadata['structural_reasons'] = engine_meta.get('structural_reasons', [])
                ctx.metadata['directional_pressure'] = engine_meta.get('directional_pressure', {})
                ctx.metadata['premature_attack'] = engine_meta.get('premature_attack', {})
                ctx.metadata['material'] = engine_meta.get('material', {})
                ctx.metadata['context'] = engine_meta.get('context', {})
                ctx.metadata['intent_hint'] = engine_meta.get('intent_hint', {})
                ctx.metadata['intent_flags'] = engine_meta.get('intent_flags', {})
                ctx.metadata['followup'] = engine_meta.get('followup', {})
                ctx.metadata['gating'] = engine_meta.get('gating', {})
                ctx.metadata['telemetry'] = engine_meta.get('telemetry', {})
                ctx.metadata['tags_initial'] = engine_meta.get('tags_initial', [])
                ctx.metadata['tags_secondary'] = engine_meta.get('tags_secondary', [])
                ctx.metadata['trigger_order'] = engine_meta.get('trigger_order', [])
                ctx.metadata['ruleset_version'] = engine_meta.get('ruleset_version', '')
                ctx.metadata['best_is_forcing'] = engine_meta.get('best_is_forcing', False)
                ctx.metadata['played_is_forcing'] = engine_meta.get('played_is_forcing', False)

            # === Fields for TensionDetector ===
            ctx.delta_eval_float = analysis_ctx.get('delta_eval_float', 0.0)
            ctx.delta_self_mobility = analysis_ctx.get('delta_self_mobility', 0.0)
            ctx.delta_opp_mobility = analysis_ctx.get('delta_opp_mobility', 0.0)
            ctx.contact_delta_played = analysis_ctx.get('contact_delta_played', 0.0)
            ctx.phase_ratio = analysis_ctx.get('phase_ratio', 0.0)
            ctx.structural_shift_signal = analysis_ctx.get('structural_shift_signal', False)
            ctx.contact_trigger = analysis_ctx.get('contact_trigger', False)
            ctx.self_trend = analysis_ctx.get('self_trend', 0.0)
            ctx.opp_trend = analysis_ctx.get('opp_trend', 0.0)
            ctx.follow_self_deltas = analysis_ctx.get('follow_self_deltas', [])
            ctx.follow_opp_deltas = analysis_ctx.get('follow_opp_deltas', [])
            ctx.followup_tail_self = analysis_ctx.get('followup_tail_self', 0.0)
            ctx.structural_compromise_dynamic = analysis_ctx.get('structural_compromise_dynamic', False)
            ctx.risk_avoidance = analysis_ctx.get('risk_avoidance', False)
            ctx.file_pressure_c_flag = analysis_ctx.get('file_pressure_c_flag', False)

            # === Fields for ProphylaxisDetector ===
            ctx.phase_bucket = analysis_ctx.get('phase_bucket', 'middlegame')

            # Merge all analysis_ctx fields into metadata (for backward compatibility)
            for key, value in analysis_ctx.items():
                if key != 'engine_meta' and key not in ctx.metadata:
                    ctx.metadata[key] = value

            # Commonly used fields (make directly accessible via metadata)
            # These are accessed via _get_field() in ProphylaxisDetector
            ctx.metadata['prophylactic_move'] = analysis_ctx.get('prophylactic_move', False)
            force_failure = analysis_ctx.get('prophylaxis_force_failure', False)
            if force_failure:
                ctx.metadata['prophylactic_move'] = True
            ctx.metadata['prophylaxis_force_failure'] = force_failure
            ctx.metadata['volatility_drop_cp'] = analysis_ctx.get('volatility_drop_cp', 0.0)
            ctx.metadata['tension_delta'] = analysis_ctx.get('tension_delta', 0.0)
            ctx.metadata['opp_mobility_drop'] = analysis_ctx.get('opp_mobility_drop', 0.0)
            ctx.metadata['structure_gain'] = analysis_ctx.get('structure_gain', 0.0)
            ctx.metadata['king_safety_gain'] = analysis_ctx.get('king_safety_gain', 0.0)
            ctx.metadata['space_gain'] = analysis_ctx.get('space_gain', 0.0)
            ctx.metadata['preventive_score'] = analysis_ctx.get('preventive_score', 0.0)
            ctx.metadata['threat_delta'] = analysis_ctx.get('threat_delta', 0.0)
            ctx.metadata['plan_drop_passed'] = analysis_ctx.get('plan_drop_passed', False)
            ctx.metadata['allow_positional'] = analysis_ctx.get('allow_positional', False)
            ctx.metadata['opp_mobility_change_eval'] = analysis_ctx.get('opp_mobility_change_eval', 0.0)
            ctx.metadata['opp_passed_exists'] = analysis_ctx.get('opp_passed_exists', False)
            ctx.metadata['blockade_established'] = analysis_ctx.get('blockade_established', False)
            ctx.metadata['opp_passed_push_drop'] = analysis_ctx.get('opp_passed_push_drop', 0.0)
            ctx.metadata['opp_line_pressure_drop'] = analysis_ctx.get('opp_line_pressure_drop', 0.0)
            ctx.metadata['break_candidates_delta'] = analysis_ctx.get('break_candidates_delta', 0.0)
            ctx.metadata['opp_tactics_change_eval'] = analysis_ctx.get('opp_tactics_change_eval', 0.0)
            ctx.metadata['self_mobility_change'] = analysis_ctx.get('self_mobility_change', 0.0)
            ctx.metadata['has_dynamic_in_band'] = analysis_ctx.get('has_dynamic_in_band', False)
            ctx.metadata['played_kind'] = analysis_ctx.get('played_kind', 'quiet')
            ctx.metadata['eval_drop_cp'] = analysis_ctx.get('eval_drop_cp', 0)
            ctx.metadata['current_ply'] = analysis_ctx.get('current_ply', 0)
            ctx.metadata['control_cfg'] = analysis_ctx.get('control_cfg', {})
            ctx.metadata['strict_mode'] = analysis_ctx.get('strict_mode', False)

            # Active piece drop fields (for simplify detector)
            ctx.metadata['captures_this_ply'] = analysis_ctx.get('captures_this_ply', 0)
            ctx.metadata['square_defended_by_opp'] = analysis_ctx.get('square_defended_by_opp', 0)
            ctx.metadata['has_immediate_tactical_followup'] = analysis_ctx.get('has_immediate_tactical_followup', False)
            ctx.metadata['is_capture'] = analysis_ctx.get('is_capture', False)
            ctx.metadata['total_active_drop'] = analysis_ctx.get('total_active_drop')
            ctx.metadata['own_active_drop'] = analysis_ctx.get('own_active_drop', 0)
            ctx.metadata['opp_active_drop'] = analysis_ctx.get('opp_active_drop', 0)
            ctx.metadata['exchange_count'] = analysis_ctx.get('exchange_count', 0)
            ctx.metadata['material_delta_self_cp'] = analysis_ctx.get('material_delta_self_cp')
            ctx.metadata['material_delta_self'] = analysis_ctx.get('material_delta_self', 0.0)
            ctx.metadata['captured_value_cp'] = analysis_ctx.get('captured_value_cp', 0)
            ctx.metadata['blockade_file'] = analysis_ctx.get('blockade_file')

            # Analysis metadata (store the full analysis_ctx including engine_meta)
            ctx.analysis_meta = analysis_ctx.copy()
            ctx.notes = {}  # Will be populated by detector

            # TODO[v2-prepare]: Extract engine candidates for preparation detector
            engine_candidates_data = analysis_ctx.get('engine_candidates', [])
            if engine_candidates_data:
                from .context import Candidate
                ctx.candidates = [
                    Candidate(
                        move=chess.Move.from_uci(c['move_uci']),
                        score_cp=c['score_cp'],
                        kind=c.get('kind', 'quiet'),
                        depth=c.get('depth', 0),
                        multipv=c.get('multipv', 0)
                    )
                    for c in engine_candidates_data
                ]
            else:
                ctx.candidates = []

        # TODO[v2-failed]: Extract maneuver-related fields from legacy_result for failure detector
        # These fields are needed for maneuver_failure detector to assess misplacement
        if hasattr(legacy_result, 'component_deltas'):
            ctx.component_deltas = dict(getattr(legacy_result, 'component_deltas', {}))
        if hasattr(legacy_result, 'opp_component_deltas'):
            ctx.opp_component_deltas = dict(getattr(legacy_result, 'opp_component_deltas', {}))
        if hasattr(legacy_result, 'metrics_played'):
            ctx.metrics_played = dict(getattr(legacy_result, 'metrics_played', {}))
        if hasattr(legacy_result, 'metrics_best'):
            ctx.metrics_best = dict(getattr(legacy_result, 'metrics_best', {}))
        if hasattr(legacy_result, 'metrics_before'):
            ctx.metrics_before = dict(getattr(legacy_result, 'metrics_before', {}))
        if hasattr(legacy_result, 'opp_metrics_played'):
            ctx.opp_metrics_played = dict(getattr(legacy_result, 'opp_metrics_played', {}))
        if hasattr(legacy_result, 'opp_metrics_best'):
            ctx.opp_metrics_best = dict(getattr(legacy_result, 'opp_metrics_best', {}))
        if hasattr(legacy_result, 'opp_metrics_before'):
            ctx.opp_metrics_before = dict(getattr(legacy_result, 'opp_metrics_before', {}))

        # Compute change_played_vs_before from metrics if not already set
        if not ctx.change_played_vs_before and ctx.metrics_played and ctx.metrics_before:
            ctx.change_played_vs_before = {
                key: ctx.metrics_played.get(key, 0.0) - ctx.metrics_before.get(key, 0.0)
                for key in ctx.metrics_played.keys()
            }
        if not ctx.opp_change_played_vs_before and ctx.opp_metrics_played and ctx.opp_metrics_before:
            ctx.opp_change_played_vs_before = {
                key: ctx.opp_metrics_played.get(key, 0.0) - ctx.opp_metrics_before.get(key, 0.0)
                for key in ctx.opp_metrics_played.keys()
            }

        return ctx

    def _build_cod_context(
        self, ctx: AnalysisContext, legacy_result: Any
    ) -> "CoDContext":
        """
        Build CoDContext from AnalysisContext for ControlOverDynamicsV2Detector.

        Args:
            ctx: AnalysisContext populated from legacy result
            legacy_result: TagResult from legacy tag_position

        Returns:
            CoDContext for CoD v2 detector
        """
        from ..cod_v2.cod_types import CoDContext, CoDMetrics

        # Extract analysis_context dict
        analysis_ctx = getattr(legacy_result, 'analysis_context', {})

        # Build CoDMetrics from legacy data
        metrics = CoDMetrics(
            opp_mobility_drop=ctx.metadata.get('opp_mobility_drop', 0.0),
            volatility_drop_cp=ctx.metadata.get('volatility_drop_cp', 0.0),
            tension_delta=ctx.metadata.get('tension_delta', 0.0),
            structure_gain=ctx.metadata.get('structure_gain', 0.0),
            king_safety_gain=ctx.metadata.get('king_safety_gain', 0.0),
            space_gain=ctx.metadata.get('space_gain', 0.0),
            preventive_score=ctx.metadata.get('preventive_score', 0.0),
            threat_delta=ctx.metadata.get('threat_delta', 0.0),
            plan_drop_passed=ctx.metadata.get('plan_drop_passed', False),
            opp_passed_exists=ctx.metadata.get('opp_passed_exists', False),
            blockade_established=ctx.metadata.get('blockade_established', False),
            opp_passed_push_drop=ctx.metadata.get('opp_passed_push_drop', 0.0),
            opp_line_pressure_drop=ctx.metadata.get('opp_line_pressure_drop', 0.0),
            break_candidates_delta=ctx.metadata.get('break_candidates_delta', 0.0),
            total_active_drop=ctx.metadata.get('total_active_drop', 0),
            own_active_drop=ctx.metadata.get('own_active_drop', 0),
            opp_active_drop=ctx.metadata.get('opp_active_drop', 0),
            exchange_count=ctx.metadata.get('exchange_count', 0),
            self_mobility_change=ctx.metadata.get('self_mobility_change', 0.0),
        )

        # Build CoDContext
        cod_ctx = CoDContext(
            board=ctx.board,
            played_move=ctx.played_move,
            actor=ctx.actor,
            metrics=metrics,
            eval_drop_cp=ctx.metadata.get('eval_drop_cp', 0),
            played_kind=ctx.metadata.get('played_kind', 'quiet'),
            current_ply=ctx.metadata.get('current_ply', 0),
            last_cod_ply=analysis_ctx.get('last_cod_ply', -999),
            phase_bucket=ctx.metadata.get('phase_bucket', 'middlegame'),
            allow_positional=ctx.metadata.get('allow_positional', False),
            has_dynamic_in_band=ctx.metadata.get('has_dynamic_in_band', False),
            control_cfg=ctx.metadata.get('control_cfg', {}),
            strict_mode=ctx.metadata.get('strict_mode', False),
        )

        return cod_ctx

    def _merge_tags(
        self, legacy_tags: List[str], new_tags: List[str], replace_patterns: List[str]
    ) -> List[str]:
        """
        Merge tags from new detectors with legacy tags.

        Args:
            legacy_tags: Tags from legacy pipeline
            new_tags: Tags from new detectors
            replace_patterns: Tag patterns to replace (e.g., ["tension_creation"])

        Returns:
            Merged list of tags with new tags taking precedence
        """
        # Remove old tags that match replace patterns
        filtered_legacy = [
            tag for tag in legacy_tags
            if not any(pattern in tag for pattern in replace_patterns)
        ]

        # Combine: new tags + filtered legacy tags
        merged = new_tags + filtered_legacy

        # Remove duplicates while preserving order
        seen = set()
        result = []
        for tag in merged:
            if tag not in seen:
                seen.add(tag)
                result.append(tag)

        return result


def run_pipeline(
    engine_path: str,
    fen: str,
    played_move_uci: str,
    depth: int = 14,
    multipv: int = 6,
    use_legacy: bool = True,
    **kwargs
) -> Dict[str, Any]:
    """
    Convenience function to run the tag detection pipeline.

    Args:
        engine_path: Path to chess engine
        fen: FEN string
        played_move_uci: Move in UCI format
        depth: Engine analysis depth
        multipv: Multi-PV count
        use_legacy: If True, use legacy implementation (default for P1)
        **kwargs: Additional arguments

    Returns:
        Result dictionary with tags, metadata, etc.
    """
    pipeline = TagDetectionPipeline(use_legacy=use_legacy)
    return pipeline.run_pipeline(
        engine_path=engine_path,
        fen=fen,
        played_move_uci=played_move_uci,
        depth=depth,
        multipv=multipv,
        **kwargs
    )
