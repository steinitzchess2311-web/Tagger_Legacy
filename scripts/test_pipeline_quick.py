"""Quick test to verify new pipeline works."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rule_tagger2.core.facade import tag_position

# Simple test case
test_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
test_move = "e2e4"

print("Testing legacy pipeline...")
try:
    result_legacy = tag_position(
        engine_path="/usr/local/bin/stockfish",
        fen=test_fen,
        played_move_uci=test_move,
        use_new=False,
    )
    print(f"✓ Legacy works")
    print(f"  tension_creation: {result_legacy.tension_creation}")
    print(f"  neutral_tension_creation: {result_legacy.neutral_tension_creation}")
except Exception as e:
    print(f"✗ Legacy failed: {e}")
    import traceback
    traceback.print_exc()

print("\nTesting new pipeline...")
try:
    result_new = tag_position(
        engine_path="/usr/local/bin/stockfish",
        fen=test_fen,
        played_move_uci=test_move,
        use_new=True,
    )
    print(f"✓ New pipeline works")
    print(f"  tension_creation: {result_new.tension_creation}")
    print(f"  neutral_tension_creation: {result_new.neutral_tension_creation}")

    # Compare
    print("\nComparison:")
    tension_match = result_legacy.tension_creation == result_new.tension_creation
    neutral_match = result_legacy.neutral_tension_creation == result_new.neutral_tension_creation

    print(f"  tension_creation match: {tension_match} ({'✓' if tension_match else '✗'})")
    print(f"  neutral_tension_creation match: {neutral_match} ({'✓' if neutral_match else '✗'})")

    if tension_match and neutral_match:
        print("\n✅ TensionDetector produces identical results!")
    else:
        print("\n❌ Mismatch detected")

except Exception as e:
    print(f"✗ New pipeline failed: {e}")
    import traceback
    traceback.print_exc()
