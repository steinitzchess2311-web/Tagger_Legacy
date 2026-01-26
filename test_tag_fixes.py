#!/usr/bin/env python3
"""
Test script to verify the tag processing fixes:
1. dynamic_over_control and control_over_dynamics should be mutually exclusive
2. control_over_dynamics parent tag should always be present with COD subtags
"""

from tag_postprocess import normalize_candidate_tags


def test_issue_1_mutual_exclusivity():
    """Test that dynamic_over_control and control_over_dynamics are mutually exclusive."""
    print("=" * 60)
    print("Test Issue 1: Mutual Exclusivity")
    print("=" * 60)

    # Test case 1: COD parent tag present, should NOT add dynamic_over_control
    tags1 = ["control_over_dynamics", "some_other_tag"]
    analysis1 = {
        "analysis_context": {
            "engine_meta": {
                "control_dynamics": {
                    "context": {
                        "has_dynamic_in_band": True,
                        "played_kind": "dynamic"
                    }
                }
            }
        }
    }
    result1 = normalize_candidate_tags(tags1, analysis1)
    has_both1 = "control_over_dynamics" in result1 and "dynamic_over_control" in result1
    print(f"\nTest 1: COD parent + dynamic conditions")
    print(f"  Input:  {tags1}")
    print(f"  Output: {result1}")
    print(f"  Has both? {has_both1} (should be False)")
    assert not has_both1, "FAIL: Both tags present!"

    # Test case 2: COD subtag (legacy format) present, should NOT add dynamic_over_control
    tags2 = ["cod_file_seal", "some_other_tag"]
    analysis2 = analysis1  # Same analysis with dynamic conditions
    result2 = normalize_candidate_tags(tags2, analysis2)
    has_both2 = any(tag.startswith("cod_") for tag in result2) and "dynamic_over_control" in result2
    print(f"\nTest 2: COD subtag (cod_file_seal) + dynamic conditions")
    print(f"  Input:  {tags2}")
    print(f"  Output: {result2}")
    print(f"  Has both? {has_both2} (should be False)")
    assert not has_both2, "FAIL: Both COD subtag and dynamic_over_control present!"

    # Test case 3: COD subtag (new format) present, should NOT add dynamic_over_control
    tags3 = ["control_over_dynamics:file_seal", "some_other_tag"]
    analysis3 = analysis1  # Same analysis with dynamic conditions
    result3 = normalize_candidate_tags(tags3, analysis3)
    has_both3 = any(tag.startswith("control_over_dynamics:") for tag in result3) and "dynamic_over_control" in result3
    print(f"\nTest 3: COD subtag (new format) + dynamic conditions")
    print(f"  Input:  {tags3}")
    print(f"  Output: {result3}")
    print(f"  Has both? {has_both3} (should be False)")
    assert not has_both3, "FAIL: Both COD subtag and dynamic_over_control present!"

    # Test case 4: No COD tags, should add dynamic_over_control
    tags4 = ["some_other_tag"]
    analysis4 = analysis1  # Same analysis with dynamic conditions
    result4 = normalize_candidate_tags(tags4, analysis4)
    has_doc4 = "dynamic_over_control" in result4
    print(f"\nTest 4: No COD tags + dynamic conditions")
    print(f"  Input:  {tags4}")
    print(f"  Output: {result4}")
    print(f"  Has dynamic_over_control? {has_doc4} (should be True)")
    assert has_doc4, "FAIL: dynamic_over_control should be added!"

    print("\n✅ All Issue 1 tests passed!")


def test_issue_2_parent_tag_presence():
    """Test that control_over_dynamics parent tag is always present with COD subtags."""
    print("\n" + "=" * 60)
    print("Test Issue 2: Parent Tag Presence")
    print("=" * 60)

    # Test case 1: COD subtag (legacy format) without parent tag
    tags1 = ["cod_file_seal", "some_other_tag"]
    analysis1 = {"analysis_context": {"engine_meta": {}}}
    result1 = normalize_candidate_tags(tags1, analysis1)
    has_parent1 = "control_over_dynamics" in result1
    has_subtag1 = "cod_file_seal" in result1
    print(f"\nTest 1: cod_file_seal without parent")
    print(f"  Input:  {tags1}")
    print(f"  Output: {result1}")
    print(f"  Has parent? {has_parent1} (should be True)")
    print(f"  Has subtag? {has_subtag1} (should be True)")
    assert has_parent1, "FAIL: Parent tag should be added!"
    assert has_subtag1, "FAIL: Subtag should be preserved!"

    # Test case 2: Multiple COD subtags without parent tag
    # Note: cod_plan_kill is in BACKGROUND_NOISE_TAGS and will be filtered out
    # when cod_file_seal (HIGH_PRIORITY_SEMANTIC_TAGS) is present
    tags2 = ["cod_regroup_consolidate", "cod_king_safety_shell", "some_other_tag"]
    analysis2 = {"analysis_context": {"engine_meta": {}}}
    result2 = normalize_candidate_tags(tags2, analysis2)
    has_parent2 = "control_over_dynamics" in result2
    subtag_count2 = sum(1 for tag in result2 if tag.startswith("cod_"))
    print(f"\nTest 2: Multiple COD subtags without parent")
    print(f"  Input:  {tags2}")
    print(f"  Output: {result2}")
    print(f"  Has parent? {has_parent2} (should be True)")
    print(f"  Subtag count: {subtag_count2} (should be 2)")
    assert has_parent2, "FAIL: Parent tag should be added!"
    assert subtag_count2 == 2, "FAIL: Both subtags should be preserved!"

    # Test case 3: COD subtag (new format) without parent tag
    tags3 = ["control_over_dynamics:file_seal", "some_other_tag"]
    analysis3 = {"analysis_context": {"engine_meta": {}}}
    result3 = normalize_candidate_tags(tags3, analysis3)
    has_parent3 = "control_over_dynamics" in result3
    has_subtag3 = "control_over_dynamics:file_seal" in result3
    print(f"\nTest 3: control_over_dynamics:file_seal without parent")
    print(f"  Input:  {tags3}")
    print(f"  Output: {result3}")
    print(f"  Has parent? {has_parent3} (should be True)")
    print(f"  Has subtag? {has_subtag3} (should be True)")
    assert has_parent3, "FAIL: Parent tag should be added!"
    assert has_subtag3, "FAIL: Subtag should be preserved!"

    # Test case 4: COD subtag with parent tag already present (no duplicate)
    tags4 = ["control_over_dynamics", "cod_file_seal", "some_other_tag"]
    analysis4 = {"analysis_context": {"engine_meta": {}}}
    result4 = normalize_candidate_tags(tags4, analysis4)
    parent_count4 = sum(1 for tag in result4 if tag == "control_over_dynamics")
    print(f"\nTest 4: Parent already present (no duplicate)")
    print(f"  Input:  {tags4}")
    print(f"  Output: {result4}")
    print(f"  Parent count: {parent_count4} (should be 1)")
    assert parent_count4 == 1, "FAIL: Parent tag should not be duplicated!"

    # Test case 5: No COD subtags, parent should not be added
    tags5 = ["some_tag", "another_tag"]
    analysis5 = {"analysis_context": {"engine_meta": {}}}
    result5 = normalize_candidate_tags(tags5, analysis5)
    has_parent5 = "control_over_dynamics" in result5
    print(f"\nTest 5: No COD subtags")
    print(f"  Input:  {tags5}")
    print(f"  Output: {result5}")
    print(f"  Has parent? {has_parent5} (should be False)")
    assert not has_parent5, "FAIL: Parent tag should not be added without subtags!"

    print("\n✅ All Issue 2 tests passed!")


def test_combined_scenarios():
    """Test combined scenarios to ensure both fixes work together."""
    print("\n" + "=" * 60)
    print("Test Combined Scenarios")
    print("=" * 60)

    # Test case 1: COD subtag + dynamic conditions
    tags1 = ["cod_file_seal"]
    analysis1 = {
        "analysis_context": {
            "engine_meta": {
                "control_dynamics": {
                    "context": {
                        "has_dynamic_in_band": True,
                        "played_kind": "dynamic"
                    }
                }
            }
        }
    }
    result1 = normalize_candidate_tags(tags1, analysis1)
    has_parent1 = "control_over_dynamics" in result1
    has_doc1 = "dynamic_over_control" in result1
    has_cod_subtag1 = "cod_file_seal" in result1
    print(f"\nTest 1: COD subtag + dynamic conditions")
    print(f"  Input:  {tags1}")
    print(f"  Output: {result1}")
    print(f"  Has parent? {has_parent1} (should be True)")
    print(f"  Has dynamic_over_control? {has_doc1} (should be False)")
    print(f"  Has cod_file_seal? {has_cod_subtag1} (should be True)")
    assert has_parent1, "FAIL: Parent should be added!"
    assert not has_doc1, "FAIL: dynamic_over_control should be excluded!"
    assert has_cod_subtag1, "FAIL: Subtag should be preserved!"

    print("\n✅ All combined scenario tests passed!")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Running Tag Processing Fix Tests")
    print("=" * 60)

    try:
        test_issue_1_mutual_exclusivity()
        test_issue_2_parent_tag_presence()
        test_combined_scenarios()

        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED! 🎉")
        print("=" * 60)
        print("\nSummary:")
        print("✅ Issue 1: dynamic_over_control and control_over_dynamics are now mutually exclusive")
        print("✅ Issue 2: control_over_dynamics parent tag is always present with COD subtags")
        print()

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
