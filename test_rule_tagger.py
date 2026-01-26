from pprint import pprint

from rule_tagger2.core.facade import tag_position
from rule_tagger2.models import StyleTracker

ENGINE = "/usr/local/bin/stockfish"
FEN = "r4rk1/1b2bppp/ppq1p3/2ppB2n/5P2/1P1BP3/P1PPQ1PP/R4RK1 w - - 0 1"
MOVE = "Bxh7"

try:
    result = tag_position(ENGINE, FEN, MOVE, depth=12, multipv=6)
    print("✅ Finished tagging successfully!")
    print("Mode:", result.mode)
    print(f"Tactical weight: {result.tactical_weight:.2f}")
    print("Primary tags:", {
        "control_over_dynamics": result.control_over_dynamics,
        "deferred_initiative": result.deferred_initiative,
        "risk_avoidance": result.risk_avoidance,
        "structural_integrity": result.structural_integrity,
        "tactical_sensitivity": result.tactical_sensitivity,
        "prophylactic_move": result.prophylactic_move,
        "initiative_exploitation": result.initiative_exploitation,
        "first_choice": result.first_choice,
        "missed_tactic": result.missed_tactic,
        "conversion_precision": result.conversion_precision,
        "panic_move": result.panic_move,
        "tactical_recovery": result.tactical_recovery,
    })
    print("Strategic metrics (play/best):")
    pprint({
        "metrics_played": result.metrics_played,
        "metrics_best": result.metrics_best,
        "component_deltas": result.component_deltas,
        "opp_metrics_played": result.opp_metrics_played,
        "opp_metrics_best": result.opp_metrics_best,
        "opp_component_deltas": result.opp_component_deltas,
    })
    print("Prophylaxis score:", result.prophylaxis_score, "coverage Δ:", result.coverage_delta)
    print("Engine meta:")
    pprint(result.analysis_context.get("engine_meta", {}))
    print("Notes:", result.notes)

    tracker = StyleTracker()
    tracker.update(result.metrics_played)
    print("🎯 Style profile snapshot:", tracker.profile())
except Exception as e:
    print("❌ Error during analysis:", e)
