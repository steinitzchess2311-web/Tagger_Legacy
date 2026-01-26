import json, os

SRC = "tests/golden_cases/cases.json"
DST_TODO = "tests/待处理的sample.json"

with open(SRC, "r", encoding="utf-8") as f:
    data = json.load(f)

def has_non_empty_expected(case):
    exp = case.get("expected_tags", None)
    return isinstance(exp, list) and len(exp) > 0

ready = [c for c in data if has_non_empty_expected(c)]
todo  = [c for c in data if not has_non_empty_expected(c)]

os.makedirs("tests", exist_ok=True)
with open(DST_TODO, "w", encoding="utf-8") as f:
    json.dump(todo, f, ensure_ascii=False, indent=2)
with open(SRC, "w", encoding="utf-8") as f:
    json.dump(ready, f, ensure_ascii=False, indent=2)

print(f"✅ kept {len(ready)} ready cases in {SRC}")
print(f"📝 moved {len(todo)} empty/missing expected cases to {DST_TODO}")
