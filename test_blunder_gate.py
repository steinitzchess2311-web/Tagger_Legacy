from core.blunder_gate import evaluate_engine_gap, forced_probabilities


def test_gate_triggers_at_threshold():
    candidates = [
        {"uci": "a2a3", "score_cp": 250},
        {"uci": "a2a4", "score_cp": 50},
    ]
    gate = evaluate_engine_gap(candidates, threshold_cp=200)
    assert gate["triggered"] is True
    assert gate["gap_cp"] == 200


def test_gate_not_triggered_below_threshold():
    candidates = [
        {"uci": "a2a3", "score_cp": 249},
        {"uci": "a2a4", "score_cp": 50},
    ]
    gate = evaluate_engine_gap(candidates, threshold_cp=200)
    assert gate["triggered"] is False
    assert gate["gap_cp"] == 199


def test_gate_requires_two_scores():
    candidates = [{"uci": "a2a3", "score_cp": 250}]
    gate = evaluate_engine_gap(candidates, threshold_cp=200)
    assert gate["triggered"] is False
    assert gate["gap_cp"] is None

    candidates = [
        {"uci": "a2a3", "score_cp": None},
        {"uci": "a2a4", "score_cp": 0},
    ]
    gate = evaluate_engine_gap(candidates, threshold_cp=200)
    assert gate["triggered"] is False
    assert gate["gap_cp"] is None


def test_forced_probabilities():
    candidates = [
        {"uci": "a2a3", "score_cp": 250},
        {"uci": "a2a4", "score_cp": 50},
        {"uci": "b2b3", "score_cp": 0},
    ]
    probs = forced_probabilities(candidates, engine1_index=0)
    assert probs == [1.0, 0.0, 0.0]
