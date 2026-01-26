from __future__ import annotations

import json

from rule_tagger2.versioning import detect_version, normalize_to_canon


def _sample_payload(version: str) -> dict:
    base = {
        "eval_before": 0.1,
        "eval_played": 0.2,
        "eval_best": 0.3,
        "tags": {"primary": ["tactical_sacrifice"]},
        "notes": {},
        "analysis_context": {
            "engine_meta": {
                "ruleset_version": version,
                "trigger_order": ["tactical_sacrifice"],
                "prophylaxis": {"components": {"preventive_score": 0.1, "effective_preventive": 0.2}},
            }
        },
    }
    return json.loads(json.dumps(base))  # deep copy


def test_detect_version_recognizes_known_versions():
    for version in ("rulestack_2025-10-20", "rulestack_2025-11-03"):
        payload = _sample_payload(version)
        assert detect_version(payload) == version


def test_normalize_to_canon_produces_canonical_record():
    payload = _sample_payload("rulestack_2025-11-03")
    record = normalize_to_canon(payload)
    assert record.ruleset_version == "rulestack_2025-11-03"
    assert record.canon_schema == "canon_v1"
    assert record.sacrifice["tactical"] is True
    assert record.prophylaxis["preventive_score"] == 0.1
